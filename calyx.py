import asyncio
import json
import logging
import logging.handlers
import os
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from functools import partial
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from calyx_notion_integration import log_trace, create_task, update_agent_health
from health_server import HealthServer
from notion_validator import validate_all_databases, print_validation_results
# Google OAuth imports
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError
from dotenv import load_dotenv
load_dotenv()
# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
def setup_logging():
    """Configure structured logging with file rotation."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    file_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/calyx.log",
        maxBytes=MAX_LOG_FILE_SIZE,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    error_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/errors.log",
        maxBytes=MAX_LOG_FILE_SIZE,
        backupCount=LOG_BACKUP_COUNT
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    return logger
logger = setup_logging()
# Discord Config
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_THE_WELL = os.getenv("CHANNEL_THE_WELL")
CHANNEL_ENGINE_LOGS = os.getenv("CHANNEL_ENGINE_LOGS")
CHANNEL_THE_SCREAM = os.getenv("CHANNEL_THE_SCREAM")
CHANNEL_THE_MIRROR = os.getenv("CHANNEL_THE_MIRROR")
CHANNEL_THE_COUNSEL = os.getenv("CHANNEL_THE_COUNSEL")
# Notion Config
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_TASK_BOARD_ID = os.getenv("NOTION_TASK_BOARD_ID")
NOTION_KNOWLEDGE_BASE_ID = os.getenv("NOTION_KNOWLEDGE_BASE_ID")
NOTION_MEMORY_ARCHIVE_ID = os.getenv("NOTION_MEMORY_ARCHIVE_ID")
NOTION_AGENT_HEALTH_ID = os.getenv("NOTION_AGENT_HEALTH_ID")
NOTION_TRACE_LOG_ID = os.getenv("NOTION_TRACE_LOG_ID")
# The Glass Journal
JOURNAL_DB_ID = os.getenv("JOURNAL_DB_ID")
# Initialize Notion client
notion = None
if NOTION_TOKEN:
    try:
        notion = NotionClient(auth=NOTION_TOKEN)
        notion.users.me()
        logger.info("Notion authentication verified")
    except Exception as e:
        logger.error(f"Notion auth failed: {e}")
        notion = None
else:
    logger.warning("NOTION_TOKEN not found in environment variables")
# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OAUTH_REDIRECT_PORT = 9090
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}/callback"
TOKEN_DIR = os.path.join(os.path.dirname(__file__), "tokens")
os.makedirs(TOKEN_DIR, exist_ok=True)
# =============================================================================
# HELPER FUNCTIONS - Safe Notion Property Access
# =============================================================================
def safe_get_notion_property(props: dict, property_name: str, property_type: str, default=None):
    """
    Safely extract a Notion property value, handling null/missing values.
    """
    try:
        prop = props.get(property_name)
        if prop is None:
            return default
        if property_type == "title":
            title_array = prop.get("title", [])
            if title_array and len(title_array) > 0:
                return title_array[0].get("text", {}).get("content", default)
            return default
        elif property_type == "rich_text":
            rich_text_array = prop.get("rich_text", [])
            if rich_text_array and len(rich_text_array) > 0:
                return rich_text_array[0].get("text", {}).get("content", default)
            return default
        elif property_type == "select":
            select_obj = prop.get("select")
            if select_obj is not None:
                return select_obj.get("name", default)
            return default
        elif property_type == "multi_select":
            multi_select_array = prop.get("multi_select", [])
            return [item.get("name") for item in multi_select_array if item.get("name")]
        elif property_type == "number":
            num_value = prop.get("number")
            return num_value if num_value is not None else default
        elif property_type == "checkbox":
            check_value = prop.get("checkbox")
            if check_value is not None:
                return check_value
            return default if default is not None else False
        elif property_type == "date":
            date_obj = prop.get("date")
            if date_obj is not None:
                return date_obj.get("start", default)
            return default
        elif property_type == "url":
            url_value = prop.get("url")
            return url_value if url_value is not None else default
        else:
            return default
    except (KeyError, TypeError, IndexError, AttributeError):
        return default
# Google OAuth scopes
GOOGLE_SCOPES = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ],
}
pending_oauth_flows = {}
OPERATIONS_PAUSED = False
last_processed_id = None
CHANNEL_TYPES = {}
def init_channel_types():
    global CHANNEL_TYPES
    CHANNEL_TYPES = {
        CHANNEL_THE_WELL: "the-well",
        CHANNEL_ENGINE_LOGS: "engine-logs",
        CHANNEL_THE_SCREAM: "the-scream",
        CHANNEL_THE_MIRROR: "the-mirror",
        CHANNEL_THE_COUNSEL: "the-counsel",
    }
def get_channel_context(channel_id: str) -> str:
    return CHANNEL_TYPES.get(str(channel_id), "unknown")
def generate_trace_id() -> str:
    return f"TRC-{uuid.uuid4().hex[:8].upper()}"
# =============================================================================
# HELPER FUNCTIONS - Logging & Notion Integration
# =============================================================================
async def log_to_engine(
    bot: commands.Bot,
    trace_id: str,
    request: str,
    agents: list,
    data_sources: list,
    result: str,
    success: bool = True,
):
    if not CHANNEL_ENGINE_LOGS:
        return None
    channel = bot.get_channel(int(CHANNEL_ENGINE_LOGS))
    if not channel:
        return None
    status_emoji = "+" if success else "x"
    agents_str = ", ".join(agents) if agents else "None"
    sources_str = ", ".join(data_sources) if data_sources else "None"
    log_message = f"""```diff
{status_emoji} [TRACE-ID: {trace_id}]
REQUEST: "{request}"
AGENTS CALLED: [{agents_str}]
DATA SOURCES: [{sources_str}]
RESULT: {result}
TIMESTAMP: {datetime.now(timezone.utc).isoformat()}
````"""
    message = await channel.send(log_message)
    return message
async def log_to_scream(
    bot: commands.Bot, error_type: str, error_msg: str, context: str = ""
):
    if not CHANNEL_THE_SCREAM:
        return
    channel = bot.get_channel(int(CHANNEL_THE_SCREAM))
    if not channel:
        return
    error_log = f"""```diff
- [ERROR: {error_type}]
MESSAGE: {error_msg}
CONTEXT: {context}
TIMESTAMP: {datetime.now(timezone.utc).isoformat()}
```"""
    await channel.send(error_log)
async def create_trace_log(
    trace_id: str,
    request: str,
    agents: list,
    data_sources: list,
    success: bool,
    discord_link: str = "",
):
    if not notion or not NOTION_TRACE_LOG_ID:
        return None
    try:
        response = notion.pages.create(
            parent={"database_id": NOTION_TRACE_LOG_ID},
            properties={
                "Trace ID": {"title": [{"text": {"content": trace_id}}]},
                "Timestamp": {
                    "date": {"start": datetime.now(timezone.utc).isoformat()}
                },
                "Request Summary": {
                    "rich_text": [{"text": {"content": request[:2000]}}]
                },
                "Agent Chain": {
                    "rich_text": [{"text": {"content": ", ".join(agents)}}]
                },
                "Data Sources Used": {
                    "multi_select": [{"name": src} for src in data_sources[:10]]
                },
                "Discord Link": {"url": discord_link if discord_link else None},
                "Success": {"checkbox": success},
            },
        )
        return response
    except APIResponseError as e:
        logger.error(f"Notion API Error (create_trace_log): {e}")
        return None
async def update_agent_health(
    agent_name: str,
    status: str = None,
    increment_execution: bool = False,
    increment_error: bool = False,
    error_message: str = None,
    auth_status: str = None,
):
    if not notion or not NOTION_AGENT_HEALTH_ID:
        return None
    try:
        response = notion.databases.query(
            database_id=NOTION_AGENT_HEALTH_ID,
            filter={"property": "Agent Name", "title": {"equals": agent_name}},
        )
        properties = {}
        if status:
            properties["Status"] = {"select": {"name": status}}
        if auth_status:
            properties["Auth Status"] = {"select": {"name": auth_status}}
        if error_message:
            properties["Last Error Message"] = {
                "rich_text": [{"text": {"content": error_message[:2000]}}]
            }
        properties["Last Execution"] = {
            "date": {"start": datetime.now(timezone.utc).isoformat()}
        }
        if response["results"]:
            page_id = response["results"][0]["id"]
            current_props = response["results"][0]["properties"]
            if increment_execution:
                current_count = safe_get_notion_property(
                    current_props, "Execution Count", "number", 0
                ) or 0
                properties["Execution Count"] = {"number": current_count + 1}
            if increment_error:
                current_errors = safe_get_notion_property(
                    current_props, "Error Count", "number", 0
                ) or 0
                properties["Error Count"] = {"number": current_errors + 1}
            notion.pages.update(page_id=page_id, properties=properties)
        else:
            properties["Agent Name"] = {"title": [{"text": {"content": agent_name}}]}
            if increment_execution:
                properties["Execution Count"] = {"number": 1}
            if increment_error:
                properties["Error Count"] = {"number": 1}
            else:
                properties["Error Count"] = {"number": 0}
                properties["Execution Count"] = {
                    "number": 1 if increment_execution else 0
                }
            notion.pages.create(
                parent={"database_id": NOTION_AGENT_HEALTH_ID}, properties=properties
            )
        return True
    except APIResponseError as e:
        logger.error(f"Notion API Error (update_agent_health): {e}")
        return None
async def query_memory_archive(memory_id: str):
    if not notion or not NOTION_MEMORY_ARCHIVE_ID:
        return None
    try:
        response = notion.databases.query(
            database_id=NOTION_MEMORY_ARCHIVE_ID,
            filter={"property": "Memory ID", "title": {"equals": memory_id}},
        )
        return response["results"][0] if response["results"] else None
    except APIResponseError as e:
        logger.error(f"Notion API Error (query_memory_archive): {e}")
        return None
async def delete_memory(page_id: str):
    if not notion:
        return False
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return True
    except APIResponseError as e:
        logger.error(f"Notion API Error (delete_memory): {e}")
        return False
async def add_to_knowledge_base(
    title: str, category: str, content: str, source: str = "Harvey Input"
):
    if not notion or not NOTION_KNOWLEDGE_BASE_ID:
        return None
    try:
        response = notion.pages.create(
            parent={"database_id": NOTION_KNOWLEDGE_BASE_ID},
            properties={
                "Entry Title": {"title": [{"text": {"content": title}}]},
                "Category": {"select": {"name": category}},
                "Source": {"select": {"name": source}},
                "Last Verified": {
                    "date": {"start": datetime.now(timezone.utc).isoformat()}
                },
                "Consent Level": {"select": {"name": "Public"}},
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ],
        )
        return response
    except APIResponseError as e:
        logger.error(f"Notion API Error (add_to_knowledge_base): {e}")
        return None
async def query_all_agent_health():
    if not notion or not NOTION_AGENT_HEALTH_ID:
        return []
    try:
        response = notion.databases.query(database_id=NOTION_AGENT_HEALTH_ID)
        return response["results"]
    except APIResponseError as e:
        logger.error(f"Notion API Error (query_all_agent_health): {e}")
        return []
async def set_all_agents_status(status: str):
    if not notion or not NOTION_AGENT_HEALTH_ID:
        return False
    try:
        agents = await query_all_agent_health()
        for agent in agents:
            notion.pages.update(
                page_id=agent["id"], properties={"Status": {"select": {"name": status}}}
            )
        return True
    except APIResponseError as e:
        logger.error(f"Notion API Error (set_all_agents_status): {e}")
        return False
async def query_trace_by_id(trace_id: str):
    if not notion or not NOTION_TRACE_LOG_ID:
        return None
    try:
        response = notion.databases.query(
            database_id=NOTION_TRACE_LOG_ID,
            filter={"property": "Trace ID", "title": {"equals": trace_id}},
        )
        return response["results"][0] if response["results"] else None
    except APIResponseError as e:
        logger.error(f"Notion API Error (query_trace_by_id): {e}")
        return None
# =============================================================================
# GOOGLE OAUTH HELPER FUNCTIONS
# =============================================================================
def create_oauth_flow(service: str) -> Flow:
    scopes = GOOGLE_SCOPES.get(service.lower(), GOOGLE_SCOPES["gmail"])
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [OAUTH_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = OAUTH_REDIRECT_URI
    return flow
def get_token_path(service: str) -> str:
    return os.path.join(TOKEN_DIR, f"{service.lower()}_token.json")
async def store_oauth_tokens(service: str, credentials: Credentials) -> bool:
    token_path = get_token_path(service)
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri or "https://oauth2.googleapis.com/token",
        "client_id": credentials.client_id or GOOGLE_CLIENT_ID,
        "client_secret": credentials.client_secret or GOOGLE_CLIENT_SECRET,
        "scopes": list(credentials.scopes) if credentials.scopes else [],
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "service": service,
    }
    try:
        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"Stored OAuth token for {service} at {token_path}")
        return True
    except Exception as e:
        logger.error(f"Error storing token to file: {e}")
        return False
async def get_oauth_tokens(service: str) -> Credentials | None:
    token_path = get_token_path(service)
    if not os.path.exists(token_path):
        logger.debug(f"No token file found for {service}")
        return None
    try:
        with open(token_path, "r") as f:
            token_data = json.load(f)
        if not token_data.get("token"):
            return None
        credentials = Credentials(
            token=token_data["token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get(
                "token_uri", "https://oauth2.googleapis.com/token"
            ),
            client_id=token_data.get("client_id", GOOGLE_CLIENT_ID),
            client_secret=token_data.get("client_secret", GOOGLE_CLIENT_SECRET),
            scopes=token_data.get("scopes", []),
        )
        if credentials.expired and credentials.refresh_token:
            logger.info(f"Refreshing expired token for {service}")
            credentials.refresh(Request())
            await store_oauth_tokens(service, credentials)
        return credentials
    except Exception as e:
        logger.error(f"Error retrieving OAuth tokens: {e}")
        return None
def list_stored_tokens() -> list:
    tokens = []
    if os.path.exists(TOKEN_DIR):
        for filename in os.listdir(TOKEN_DIR):
            if filename.endswith("_token.json"):
                service = filename.replace("_token.json", "")
                token_path = os.path.join(TOKEN_DIR, filename)
                try:
                    with open(token_path, "r") as f:
                        data = json.load(f)
                    tokens.append(
                        {
                            "service": service,
                            "stored_at": data.get("stored_at"),
                            "has_refresh": bool(data.get("refresh_token")),
                        }
                    )
                except:
                    tokens.append({"service": service, "error": "Could not read"})
    return tokens
async def run_oauth_callback_server(flow: Flow, timeout: int = 120) -> str | None:
    from aiohttp import web
    auth_code = None
    auth_event = asyncio.Event()
    async def callback_handler(request):
        nonlocal auth_code
        auth_code = request.query.get("code")
        if auth_code:
            auth_event.set()
            return web.Response(
                text="<html><body><h1>Authorization Successful!</h1>"
                "<p>You can close this window and return to Discord.</p></body></html>",
                content_type="text/html",
            )
        else:
            error = request.query.get("error", "Unknown error")
            return web.Response(
                text=f"<html><body><h1>Authorization Failed</h1><p>{error}</p></body></html>",
                content_type="text/html",
            )
    app = web.Application()
    app.router.add_get("/callback", callback_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", OAUTH_REDIRECT_PORT)
    try:
        await site.start()
        logger.info(f"OAuth callback server started on port {OAUTH_REDIRECT_PORT}")
        try:
            await asyncio.wait_for(auth_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("OAuth callback timed out")
            return None
        return auth_code
    finally:
        await runner.cleanup()
async def export_all_databases():
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "databases": {},
    }
    if not notion:
        return export_data
    db_mapping = {
        "task_board": NOTION_TASK_BOARD_ID,
        "knowledge_base": NOTION_KNOWLEDGE_BASE_ID,
        "memory_archive": NOTION_MEMORY_ARCHIVE_ID,
        "agent_health": NOTION_AGENT_HEALTH_ID,
        "trace_log": NOTION_TRACE_LOG_ID,
    }
    for name, db_id in db_mapping.items():
        if db_id:
            try:
                response = notion.databases.query(database_id=db_id)
                export_data["databases"][name] = {
                    "count": len(response["results"]),
                    "entries": [
                        {
                            "id": page["id"],
                            "properties": page["properties"],
                            "created_time": page["created_time"],
                            "last_edited_time": page["last_edited_time"],
                        }
                        for page in response["results"]
                    ],
                }
            except APIResponseError as e:
                export_data["databases"][name] = {"error": str(e)}
    return export_data
# =============================================================================
# BOT CLASS
# =============================================================================
class CalyxBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        logger.info(f"Synced slash commands for {self.user}")
bot = CalyxBot()
health_server = None
# =============================================================================
# VIEWS (for button confirmations)
# =============================================================================
class PurgeConfirmView(View):
    def __init__(self, memory_id: str, page_id: str, memory_preview: str):
        super().__init__(timeout=60)
        self.memory_id = memory_id
        self.page_id = page_id
        self.memory_preview = memory_preview
        self.confirmed = False
    @discord.ui.button(
        label="Confirm Purge", style=discord.ButtonStyle.danger, emoji="\\U0001f5d1"
    )
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        success = await delete_memory(self.page_id)
        trace_id = generate_trace_id()
        if success:
            await log_to_engine(
                bot,
                trace_id,
                f"Purge memory: {self.memory_id}",
                ["MemoryManager"],
                ["Memory Archive"],
                f"Success - Memory {self.memory_id} purged",
            )
            await create_trace_log(
                trace_id,
                f"Purge memory: {self.memory_id}",
                ["MemoryManager"],
                ["Memory Archive"],
                True,
            )
            await interaction.response.edit_message(
                content=f"Memory {self.memory_id} has been permanently purged.",
                view=None,
            )
        else:
            await log_to_scream(
                bot, "PURGE_FAILED", f"Failed to purge memory {self.memory_id}"
            )
            await interaction.response.edit_message(
                content=f"Failed to purge memory {self.memory_id}. Check #the-scream for details.",
                view=None,
            )
        self.stop()
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=f"Purge cancelled. Memory {self.memory_id} retained.", view=None
        )
        self.stop()
# =============================================================================
# EVENT HANDLERS
# =============================================================================
@bot.event
async def on_ready():
    global health_server
    init_channel_types()
    logger.info(f"Calyx Online: {bot.user}")
    logger.info(f"Operations Paused: {OPERATIONS_PAUSED}")
    if notion:
        database_ids = {
            "task_board": NOTION_TASK_BOARD_ID,
            "trace_log": NOTION_TRACE_LOG_ID,
            "agent_health": NOTION_AGENT_HEALTH_ID,
            "knowledge_base": NOTION_KNOWLEDGE_BASE_ID,
            "memory_archive": NOTION_MEMORY_ARCHIVE_ID
        }
        validation_results = validate_all_databases(notion, database_ids)
        print_validation_results(validation_results)
    else:
        logger.warning("Notion client not configured - skipping schema validation")
    await update_agent_health("Calyx", status="Active", increment_execution=True)
    if not health_server:
        health_server = HealthServer(bot, notion, port=8080)
        await health_server.start()
        logger.info("Health check endpoints available at http://localhost:8080/health")
    if notion and not poll_glass_journal.is_running():
        poll_glass_journal.start()
        logger.info("Broadcast Protocol Active - polling The Glass Journal")
    if CHANNEL_THE_MIRROR:
        channel = bot.get_channel(int(CHANNEL_THE_MIRROR))
        if channel:
            embed = discord.Embed(
                title="Calyx System Boot",
                description="All systems nominal. Awaiting instructions.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Notion Integration",
                value="Connected" if notion else "Not configured",
                inline=True,
            )
            embed.add_field(
                name="Operations",
                value="Paused" if OPERATIONS_PAUSED else "Active",
                inline=True,
            )
            await channel.send(embed=embed)
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if OPERATIONS_PAUSED and not message.content.startswith("!"):
        return
    channel_type = get_channel_context(str(message.channel.id))
    if channel_type == "the-well":
        pass
    elif channel_type == "the-counsel":
        pass
    await bot.process_commands(message)
# =============================================================================
# BROADCAST PULSE (Notion Journal Polling)
# =============================================================================
@tasks.loop(minutes=5)
async def poll_glass_journal():
    global last_processed_id
    if not notion:
        return
    if not JOURNAL_DB_ID:
        return
    if not CHANNEL_ENGINE_LOGS:
        return
    channel = bot.get_channel(int(CHANNEL_ENGINE_LOGS))
    if not channel:
        return
    try:
        res = notion.databases.query(
            database_id=JOURNAL_DB_ID,
            sorts=[{"timestamp": "created_time", "direction": "descending"}],
            page_size=1
        )
        if res["results"]:
            latest_page = res["results"][0]
            page_id = latest_page["id"]
            if page_id != last_processed_id:
                props = latest_page["properties"]
                title = safe_get_notion_property(props, "Name", "title", "Untitled")
                url = f"https://www.notion.so/{page_id.replace('-', '')}"
                message = f"**[SYSTEM LOG]** New entry detected in The Glass Journal:\\n**{title}**\\nView: {url}"
                await channel.send(message)
                last_processed_id = page_id
    except Exception as e:
        logger.error(f"Broadcast Error ({type(e).__name__}): {e}")
# =============================================================================
# SLASH COMMANDS
# =============================================================================
@bot.tree.command(
    name="auth", description="Authenticate/re-auth service (Gmail, Calendar, etc)"
)
@app_commands.describe(
    service="The service to authenticate (e.g., gmail, calendar, notion)"
)
@app_commands.choices(
    service=[
        app_commands.Choice(name="gmail", value="gmail"),
        app_commands.Choice(name="calendar", value="calendar"),
        app_commands.Choice(name="notion", value="notion"),
    ]
)
async def auth(interaction: discord.Interaction, service: str):
    trace_id = generate_trace_id()
    service_lower = service.lower()
    await log_to_engine(
        bot,
        trace_id,
        f"Auth request: {service}",
        ["AuthManager"],
        ["Agent Health"],
        f"Initiated auth flow for {service}",
    )
    if service_lower == "notion":
        status = "Valid" if notion else "Invalid"
        await update_agent_health(
            "NotionService", auth_status=status, increment_execution=True
        )
        embed = discord.Embed(
            title="Authentication: Notion",
            description="Notion is configured via NOTION_TOKEN in .env",
            color=discord.Color.green() if notion else discord.Color.red(),
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if service_lower in ["gmail", "calendar"]:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            await interaction.response.send_message(
                "Google OAuth not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env",
                ephemeral=True,
            )
            return
        existing_creds = await get_oauth_tokens(service_lower)
        if existing_creds and existing_creds.valid:
            await update_agent_health(
                f"{service.capitalize()}Service",
                auth_status="Valid",
                increment_execution=True,
            )
            embed = discord.Embed(
                title=f"Authentication: {service.capitalize()}",
                description=f"Already authenticated with {service.capitalize()}!",
                color=discord.Color.green(),
            )
            embed.add_field(name="Status", value="Valid", inline=True)
            embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
            embed.set_footer(text="Run /auth again to re-authenticate if needed.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            flow = create_oauth_flow(service_lower)
            auth_url, _ = flow.authorization_url(
                access_type="offline", include_granted_scopes="true", prompt="consent"
            )
            pending_oauth_flows[interaction.user.id] = {
                "flow": flow,
                "service": service_lower,
                "trace_id": trace_id,
            }
            embed = discord.Embed(
                title=f"Authenticate {service.capitalize()}",
                description="Click the link below to authorize access.\\n\\n"
                "**Important:** After authorizing, you'll be redirected to localhost. "
                "Make sure the bot is running locally to receive the callback.",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Authorization URL",
                value=f"[Click here to authorize]({auth_url})",
                inline=False,
            )
            embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
            embed.add_field(name="Timeout", value="2 minutes", inline=True)
            embed.set_footer(text="Waiting for authorization...")
            await interaction.followup.send(embed=embed, ephemeral=True)
            auth_code = await run_oauth_callback_server(flow, timeout=120)
            if auth_code:
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials
                stored = await store_oauth_tokens(service_lower, credentials)
                if stored:
                    await update_agent_health(
                        f"{service.capitalize()}Service",
                        auth_status="Valid",
                        increment_execution=True,
                    )
                    await log_to_engine(
                        bot,
                        trace_id,
                        f"OAuth completed: {service}",
                        ["AuthManager", "OAuthHandler"],
                        ["Memory Archive"],
                        f"Success - {service.capitalize()} tokens stored",
                    )
                    await create_trace_log(
                        trace_id,
                        f"OAuth completed: {service}",
                        ["AuthManager", "OAuthHandler"],
                        ["Memory Archive"],
                        True,
                    )
                    success_embed = discord.Embed(
                        title=f"{service.capitalize()} Authenticated!",
                        description=f"Successfully connected to {service.capitalize()}. Tokens stored securely.",
                        color=discord.Color.green(),
                    )
                    success_embed.add_field(
                        name="Trace ID", value=f"{trace_id}", inline=True
                    )
                    await interaction.followup.send(embed=success_embed, ephemeral=True)
                else:
                    await interaction.followup.send(
                        f"Authorization successful but failed to store tokens. Check #the-scream.",
                        ephemeral=True,
                    )
            else:
                await update_agent_health(
                    f"{service.capitalize()}Service",
                    auth_status="Expired",
                    increment_error=True,
                    error_message="OAuth flow timed out",
                )
                await interaction.followup.send(
                    "Authorization timed out. Please try /auth again.", ephemeral=True
                )
        except Exception as e:
            await log_to_scream(bot, "OAUTH_ERROR", str(e), f"Service: {service}")
            await update_agent_health(
                f"{service.capitalize()}Service",
                auth_status="Invalid",
                increment_error=True,
                error_message=str(e)[:500],
            )
            await interaction.followup.send(
                f"OAuth error: {str(e)[:200]}\\n\\nCheck #the-scream for details.",
                ephemeral=True,
            )
        finally:
            pending_oauth_flows.pop(interaction.user.id, None)
        return
    await update_agent_health(
        f"{service.capitalize()}Service", auth_status="N/A", increment_execution=True
    )
    embed = discord.Embed(
        title=f"Authentication: {service.capitalize()}",
        description=f"Auth flow for {service} is not yet implemented.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)
@bot.tree.command(
    name="soul", description="Adjust alignment parameter (e.g., verbosity high)"
)
@app_commands.describe(
    parameter="Parameter to adjust (verbosity, tone, formality, proactivity)",
    value="New value for parameter",
)
@app_commands.choices(
    parameter=[
        app_commands.Choice(name="verbosity", value="verbosity"),
        app_commands.Choice(name="tone", value="tone"),
        app_commands.Choice(name="formality", value="formality"),
        app_commands.Choice(name="proactivity", value="proactivity"),
    ]
)
async def soul(interaction: discord.Interaction, parameter: str, value: str):
    await interaction.response.defer(ephemeral=True)
    trace_id = generate_trace_id()
    result = await add_to_knowledge_base(
        title=f"Preference: {parameter}",
        category="Personal",
        content=f"{parameter} = {value}\\n\\nSet by Harvey on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        source="Harvey Input",
    )
    success = result is not None
    discord_msg = await log_to_engine(
        bot,
        trace_id,
        f"Soul adjustment: {parameter} -> {value}",
        ["SoulManager", "KnowledgeBase"],
        ["Knowledge Base"],
        "Success - Preference updated" if success else "Failed - Could not update",
        success=success,
    )
    await create_trace_log(
        trace_id,
        f"Soul adjustment: {parameter} -> {value}",
        ["SoulManager", "KnowledgeBase"],
        ["Knowledge Base"],
        success,
        discord_link=discord_msg.jump_url if discord_msg else "",
    )
    if success:
        embed = discord.Embed(
            title="Soul Alignment Shift",
            description=f"**{parameter}** has been set to {value}",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        embed.set_footer(text="Preference stored in Knowledge Base.")
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await log_to_scream(
            bot,
            "SOUL_UPDATE_FAILED",
            f"Could not update {parameter} to {value}",
            f"Trace: {trace_id}",
        )
        await interaction.followup.send(
            f"Failed to update soul parameter. Check #the-scream for details.\\nTrace: {trace_id}",
            ephemeral=True,
        )
@bot.tree.command(name="trace", description="Get raw logs for specific trace ID")
@app_commands.describe(trace_id="The trace ID to look up (e.g., TRC-ABC12345)")
async def trace(interaction: discord.Interaction, trace_id: str):
    trace_data = await query_trace_by_id(trace_id)
    if trace_data:
        props = trace_data["properties"]
        request = safe_get_notion_property(props, "Request Summary", "rich_text", "N/A")
        agents = safe_get_notion_property(props, "Agent Chain", "rich_text", "N/A")
        sources = safe_get_notion_property(props, "Data Sources Used", "multi_select", [])
        success = safe_get_notion_property(props, "Success", "checkbox", False)
        timestamp = safe_get_notion_property(props, "Timestamp", "date", "N/A")
        discord_link = safe_get_notion_property(props, "Discord Link", "url", "")
        embed = discord.Embed(
            title=f"Trace: {trace_id}",
            color=discord.Color.green() if success else discord.Color.red(),
        )
        embed.add_field(name="Request", value=request[:1024], inline=False)
        embed.add_field(name="Agents", value=agents, inline=True)
        embed.add_field(
            name="Data Sources",
            value=", ".join(sources) if sources else "None",
            inline=True,
        )
        embed.add_field(
            name="Result", value="Success" if success else "Failed", inline=True
        )
        embed.add_field(name="Timestamp", value=timestamp, inline=False)
        if discord_link:
            embed.add_field(
                name="Discord Log",
                value=f"[Jump to message]({discord_link})",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            f"No trace found for ID: {trace_id}\\n\\n"
            "Trace IDs are formatted as TRC-XXXXXXXX. "
            "Check #engine-logs for recent traces.",
            ephemeral=True,
        )
@bot.tree.command(
    name="status", description="Show all agent health + last execution times"
)
async def status(interaction: discord.Interaction):
    # Defer response immediately since Notion queries may take >3 seconds
    await interaction.response.defer()
    agents = await query_all_agent_health()
    embed = discord.Embed(
        title="Vessel System Status",
        color=discord.Color.green()
        if not OPERATIONS_PAUSED
        else discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Operations",
        value="PAUSED" if OPERATIONS_PAUSED else "ACTIVE",
        inline=True,
    )
    embed.add_field(
        name="Discord Latency", value=f"{round(bot.latency * 1000)}ms", inline=True
    )
    embed.add_field(
        name="Notion", value="Connected" if notion else "Disconnected", inline=True
    )
    if agents:
        for agent in agents[:10]:
            props = agent["properties"]
            name = safe_get_notion_property(props, "Agent Name", "title", "Unknown")
            agent_status = safe_get_notion_property(props, "Status", "select", "Unknown")
            exec_count = safe_get_notion_property(props, "Execution Count", "number", 0)
            error_count = safe_get_notion_property(props, "Error Count", "number", 0)
            auth = safe_get_notion_property(props, "Auth Status", "select", "N/A")
            status_emoji = {
                "Active": "\\U00002705",
                "Paused": "\\U000023f8",
                "Error": "\\U0000274c",
                "Disabled": "\\U000026d4",
            }.get(agent_status, "\\U00002753")
            embed.add_field(
                name=f"{status_emoji} {name}",
                value=f"Status: {agent_status}\\nRuns: {exec_count} | Errors: {error_count}\\nAuth: {auth}",
                inline=True,
            )
    else:
        embed.add_field(
            name="Agents",
            value="No agents registered in Agent Health Monitor.\\nRun commands to auto-register agents.",
            inline=False,
        )
    embed.set_footer(text="Use /pause to suspend operations, /resume to continue.")
    await interaction.followup.send(embed=embed)
@bot.tree.command(
    name="pause", description="Temporarily suspend all automated triggers"
)
async def pause(interaction: discord.Interaction):
    global OPERATIONS_PAUSED
    trace_id = generate_trace_id()
    # Defer response immediately since Notion operations may take >3 seconds
    await interaction.response.defer()
    OPERATIONS_PAUSED = True
    await set_all_agents_status("Paused")
    await log_to_engine(
        bot,
        trace_id,
        "System pause requested",
        ["SystemController"],
        ["Agent Health"],
        "Success - All operations paused",
    )
    await create_trace_log(
        trace_id, "System pause requested", ["SystemController"], ["Agent Health"], True
    )
    embed = discord.Embed(
        title="Operations Suspended",
        description="All automated triggers are now offline.\\n\\nSlash commands remain available.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
    embed.set_footer(text="Use /resume to re-enable operations.")
    await interaction.followup.send(embed=embed)
@bot.tree.command(name="resume", description="Re-enable automated operations")
async def resume(interaction: discord.Interaction):
    global OPERATIONS_PAUSED
    trace_id = generate_trace_id()
    # Defer response immediately since Notion operations may take >3 seconds
    await interaction.response.defer()
    OPERATIONS_PAUSED = False
    await set_all_agents_status("Active")
    await log_to_engine(
        bot,
        trace_id,
        "System resume requested",
        ["SystemController"],
        ["Agent Health"],
        "Success - All operations resumed",
    )
    await create_trace_log(
        trace_id,
        "System resume requested",
        ["SystemController"],
        ["Agent Health"],
        True,
    )
    embed = discord.Embed(
        title="Operations Resumed",
        description="Calyx is back in the driver's seat.\\n\\nAll automated triggers are now online.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
    await interaction.followup.send(embed=embed)
@bot.tree.command(
    name="purge", description="Delete specific memory (requires confirmation)"
)
@app_commands.describe(memory_id="The unique ID of the memory to purge")
async def purge(interaction: discord.Interaction, memory_id: str):
    memory = await query_memory_archive(memory_id)
    if not memory:
        await interaction.response.send_message(
            f"Memory {memory_id} not found in Memory Archive.\n\n"
            "Check the Memory ID and try again.",
            ephemeral=True,
        )
        return
    props = memory["properties"]
    mem_type = safe_get_notion_property(props, "Type", "select", "Unknown")
    consent = safe_get_notion_property(props, "Consent Status", "select", "Unknown")
    preview = safe_get_notion_property(props, "Content Preview", "rich_text", "No preview available")
    embed = discord.Embed(
        title=f"Confirm Purge: {memory_id}",
        description="This action is irreversible. The memory will be permanently deleted.",
        color=discord.Color.red(),
    )
    embed.add_field(name="Type", value=mem_type, inline=True)
    embed.add_field(name="Consent Status", value=consent, inline=True)
    embed.add_field(name="Preview", value=preview[:500], inline=False)
    view = PurgeConfirmView(memory_id, memory["id"], preview)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
@bot.tree.command(name="export", description="Generate full data dump for backup")
async def export(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    trace_id = generate_trace_id()
    export_data = await export_all_databases()
    export_data["trace_id"] = trace_id
    json_str = json.dumps(export_data, indent=2, default=str)
    db_count = len([k for k, v in export_data["databases"].items() if "error" not in v])
    await log_to_engine(
        bot,
        trace_id,
        "Full data export requested",
        ["ExportManager"],
        list(export_data["databases"].keys()),
        f"Success - Exported {db_count} databases",
    )
    await create_trace_log(
        trace_id,
        "Full data export requested",
        ["ExportManager"],
        list(export_data["databases"].keys()),
        True,
    )
    filename = f"vessel_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file = discord.File(
        fp=__import__("io").BytesIO(json_str.encode()), filename=filename
    )
    embed = discord.Embed(
        title="Data Export Complete",
        description=f"Exported {db_count} databases to JSON.",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
    embed.add_field(name="File", value=filename, inline=True)
    summary_lines = []
    for name, data in export_data["databases"].items():
        if "error" in data:
            summary_lines.append(f"- {name}: Error")
        else:
            summary_lines.append(f"- {name}: {data['count']} entries")
    embed.add_field(name="Contents", value="\\n".join(summary_lines), inline=False)
    await interaction.followup.send(embed=embed, file=file, ephemeral=True)
# =============================================================================
# CODE EXECUTION COMMANDS
# =============================================================================
SHELL_BLACKLIST = [
    "rm -rf",
    "rm -r /",
    "dd if=",
    "mkfs",
    "> /dev/",
    ":(){ :|:& };:",
    "mv /* ",
    "chmod -R 777 /",
]
@bot.tree.command(name="exec", description="Execute Python code (30s timeout)")
@app_commands.describe(code="Python code to execute")
async def execute_code(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=False)
    trace_id = generate_trace_id()
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_file = f.name
            f.write(code)
        try:
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                timeout=30,
                text=True
            )
            stdout = result.stdout if result.stdout else "(no output)"
            stderr = result.stderr if result.stderr else ""
            return_code = result.returncode
            success = return_code == 0
            max_length = 1800
            if len(stdout) > max_length:
                stdout = stdout[:max_length] + "\\n... (output truncated)"
            if len(stderr) > max_length:
                stderr = stderr[:max_length] + "\\n... (output truncated)"
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = "Execution timed out after 30 seconds"
            return_code = -1
            success = False
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
        color = discord.Color.green() if success else discord.Color.red()
        embed = discord.Embed(
            title="Python Code Execution",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        code_preview = code if len(code) <= 500 else code[:500] + "\\n... (truncated)"
        embed.add_field(name="Code", value=f"```python\\n{code_preview}\\n```", inline=False)
        if stdout:
            embed.add_field(name="Output", value=f"```\\n{stdout}\\n```", inline=False)
        if stderr:
            embed.add_field(name="Errors", value=f"```\\n{stderr}\\n```", inline=False)
        embed.add_field(name="Return Code", value=f"{return_code}", inline=True)
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        result_msg = "Success" if success else f"Failed (code {return_code})"
        await log_to_engine(
            bot, trace_id, f"Python code execution: {code[:50]}...",
            ["CodeExecutor"], ["Python Runtime"], result_msg, success
        )
        await create_trace_log(
            trace_id, "Execute Python code", ["CodeExecutor"], ["Python Runtime"], success
        )
        await update_agent_health(
            "CodeExecutor",
            status="Active" if success else "Error",
            increment_execution=True,
            increment_error=not success,
            error_message=stderr if not success else None
        )
        if not success:
            await log_to_scream(
                bot, "Code Execution Error",
                f"Python code execution failed\\nTrace: {trace_id}\\nError: {stderr[:200]}",
                f"Return code: {return_code}"
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Exec command error: {e}", exc_info=True)
        embed = discord.Embed(
            title="Execution Error",
            description=f"Failed to execute code: {str(e)}",
            color=discord.Color.red()
        )
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        await interaction.followup.send(embed=embed)
        await log_to_scream(
            bot, "Code Execution System Error",
            f"Exec command crashed\\nTrace: {trace_id}\\nError: {str(e)}"
        )
@bot.tree.command(name="shell", description="Execute shell command (30s timeout)")
@app_commands.describe(command="Shell command to execute")
async def execute_shell(interaction: discord.Interaction, command: str):
    await interaction.response.defer(ephemeral=False)
    trace_id = generate_trace_id()
    for pattern in SHELL_BLACKLIST:
        if pattern in command.lower():
            embed = discord.Embed(
                title="Command Blocked",
                description="This command contains a dangerous pattern and has been blocked for safety.",
                color=discord.Color.red()
            )
            embed.add_field(name="Blocked Pattern", value=f"{pattern}", inline=False)
            embed.add_field(name="Command", value=f"```bash\\n{command}\\n```", inline=False)
            embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
            await interaction.followup.send(embed=embed)
            await log_to_engine(
                bot, trace_id, f"Blocked dangerous shell command: {command[:50]}...",
                ["ShellExecutor"], ["Security Filter"],
                f"Blocked - dangerous pattern: {pattern}", False
            )
            return
    try:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, timeout=30, text=True
            )
            stdout = result.stdout if result.stdout else "(no output)"
            stderr = result.stderr if result.stderr else ""
            return_code = result.returncode
            success = return_code == 0
            max_length = 1800
            if len(stdout) > max_length:
                stdout = stdout[:max_length] + "\\n... (output truncated)"
            if len(stderr) > max_length:
                stderr = stderr[:max_length] + "\\n... (output truncated)"
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = "Command timed out after 30 seconds"
            return_code = -1
            success = False
        color = discord.Color.green() if success else discord.Color.red()
        embed = discord.Embed(
            title="Shell Command Execution",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Command", value=f"```bash\\n{command}\\n```", inline=False)
        if stdout:
            embed.add_field(name="Output", value=f"```\\n{stdout}\\n```", inline=False)
        if stderr:
            embed.add_field(name="Errors", value=f"```\\n{stderr}\\n```", inline=False)
        embed.add_field(name="Return Code", value=f"{return_code}", inline=True)
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        result_msg = "Success" if success else f"Failed (code {return_code})"
        await log_to_engine(
            bot, trace_id, f"Shell command execution: {command[:50]}...",
            ["ShellExecutor"], ["System Shell"], result_msg, success
        )
        await create_trace_log(
            trace_id, "Execute shell command", ["ShellExecutor"], ["System Shell"], success
        )
        await update_agent_health(
            "ShellExecutor",
            status="Active" if success else "Error",
            increment_execution=True,
            increment_error=not success,
            error_message=stderr if not success else None
        )
        if not success:
            await log_to_scream(
                bot, "Shell Command Error",
                f"Shell command failed\\nTrace: {trace_id}\\nError: {stderr[:200]}",
                f"Return code: {return_code}"
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Shell command error: {e}", exc_info=True)
        embed = discord.Embed(
            title="Execution Error",
            description=f"Failed to execute command: {str(e)}",
            color=discord.Color.red()
        )
        embed.add_field(name="Trace ID", value=f"{trace_id}", inline=True)
        await interaction.followup.send(embed=embed)
        await log_to_scream(
            bot, "Shell Execution System Error",
            f"Shell command crashed\\nTrace: {trace_id}\\nError: {str(e)}"
        )
@bot.tree.command(name="ping", description="Check bot latency and system health")
async def ping(interaction: discord.Interaction):
    """Quick health check with latency metrics."""
    trace_id = generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    # Calculate Discord websocket latency
    ws_latency = bot.latency * 1000  # Convert to ms
    
    # Test Notion connectivity
    notion_status = "✅ Connected"
    notion_latency = None
    try:
        notion_start = datetime.now(timezone.utc)
        notion.users.me()
        notion_latency = (datetime.now(timezone.utc) - notion_start).total_seconds() * 1000
    except Exception as e:
        notion_status = f"❌ Error: {str(e)[:50]}"
    
    # Calculate total response time
    total_latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    # Create embed
    embed = discord.Embed(
        title="🏓 Pong!",
        description="Calyx system health check",
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Discord Latency", value=f"{ws_latency:.1f} ms", inline=True)
    embed.add_field(name="Response Time", value=f"{total_latency:.1f} ms", inline=True)
    embed.add_field(name="Notion", value=notion_status, inline=False)
    if notion_latency:
        embed.add_field(name="Notion Latency", value=f"{notion_latency:.1f} ms", inline=True)
    embed.add_field(name="Trace ID", value=trace_id, inline=True)
    embed.set_footer(text=f"Calyx v1.0 | Uptime: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Log the ping
    await log_to_engine(
        bot, trace_id, "Health check (ping)",
        ["HealthMonitor"], ["System"],
        f"Discord: {ws_latency:.1f}ms | Notion: {notion_latency:.1f}ms" if notion_latency else "Discord only",
        success=True
    )
    await create_trace_log(
        trace_id, "Health check ping", ["HealthMonitor"], ["System"], True
    )


@bot.tree.command(name="remember", description="Save a memory to the Memory Archive")
@app_commands.describe(
    content="The memory to save",
    memory_type="Type of memory (optional)",
    retention="How long to keep this memory (optional)"
)
@app_commands.choices(
    memory_type=[
        app_commands.Choice(name="insight", value="Insight"),
        app_commands.Choice(name="conversation", value="Conversation"),
        app_commands.Choice(name="observation", value="Observation"),
        app_commands.Choice(name="reference", value="Reference"),
    ],
    retention=[
        app_commands.Choice(name="7 days", value="7 Days"),
        app_commands.Choice(name="30 days", value="30 Days"),
        app_commands.Choice(name="1 year", value="1 Year"),
        app_commands.Choice(name="permanent", value="Permanent"),
    ]
)
async def remember(
    interaction: discord.Interaction,
    content: str,
    memory_type: str = "Insight",
    retention: str = "Permanent"
):
    """Save a memory to Notion Memory Archive."""
    await interaction.response.defer(ephemeral=True)
    trace_id = generate_trace_id()
    
    if not notion:
        await interaction.followup.send(
            "❌ Notion integration is not available.", ephemeral=True
        )
        return
    
    try:
        # Create memory in Notion
        memory_id = f"MEM-{uuid.uuid4().hex[:8].upper()}"
        notion.pages.create(
            parent={"database_id": NOTION_MEMORY_ARCHIVE_ID},
            properties={
                "Memory ID": {"title": [{"text": {"content": memory_id}}]},
                "Type": {"select": {"name": memory_type}},
                "Consent Status": {"select": {"name": "Explicit"}},
                "Created Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Last Accessed": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Access Count": {"number": 1},
                "Retention Policy": {"select": {"name": retention}},
                "Content Preview": {
                    "rich_text": [{"text": {"content": content[:500]}}]
                },
            }
        )
        
        # Create embed response
        embed = discord.Embed(
            title="🧠 Memory Saved",
            description=f"Saved to Memory Archive",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Memory ID", value=memory_id, inline=True)
        embed.add_field(name="Type", value=memory_type, inline=True)
        embed.add_field(name="Retention", value=retention, inline=True)
        embed.add_field(name="Content", value=f"{content[:500]}{'...' if len(content) > 500 else ''}", inline=False)
        embed.add_field(name="Trace ID", value=trace_id, inline=True)
        embed.set_footer(text="Use /purge to delete this memory if needed")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log to engine
        await log_to_engine(
            bot, trace_id, f"Memory saved: {memory_id}",
            ["MemoryManager"], ["Memory Archive"],
            f"Type: {memory_type}, Retention: {retention}",
            success=True
        )
        await create_trace_log(
            trace_id, "Save memory", ["MemoryManager"], ["Memory Archive"], True
        )
        
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")
        await log_to_scream(bot, "MEMORY_SAVE_FAILED", str(e)[:200], f"Trace: {trace_id}")
        await interaction.followup.send(
            f"❌ Failed to save memory. Check #the-scream for details.\nTrace: {trace_id}",
            ephemeral=True
        )


@bot.tree.command(name="task", description="Create a new task in the Task Board")
@app_commands.describe(
    name="Name of the task",
    priority="Task priority (default: Medium)",
    assigned_to="Who should do this (default: Calyx)"
)
@app_commands.choices(
    priority=[
        app_commands.Choice(name="Critical", value="Critical"),
        app_commands.Choice(name="High", value="High"),
        app_commands.Choice(name="Medium", value="Medium"),
        app_commands.Choice(name="Low", value="Low"),
    ],
    assigned_to=[
        app_commands.Choice(name="tinyNature", value="tinyNature"),
        app_commands.Choice(name="Calyx", value="Calyx"),
        app_commands.Choice(name="Harvey", value="Harvey"),
        app_commands.Choice(name="Claude", value="Claude"),
        app_commands.Choice(name="Other", value="Other"),
    ]
)
async def task(
    interaction: discord.Interaction,
    name: str,
    priority: str = "Medium",
    assigned_to: str = "Calyx"
):
    """Create a task in Notion Task Board."""
    await interaction.response.defer(ephemeral=True)
    trace_id = generate_trace_id()
    
    # Use the existing create_task function
    result = await create_task(
        task_name=name,
        status="To-Do",
        priority=priority,
        assigned_to=assigned_to,
        trigger_source="Manual",
        trace_link=None
    )
    
    success = result is not None
    
    if success:
        # Color based on priority
        color_map = {
            "Critical": discord.Color.dark_red(),
            "High": discord.Color.red(),
            "Medium": discord.Color.orange(),
            "Low": discord.Color.green(),
        }
        
        embed = discord.Embed(
            title="✅ Task Created",
            description=f"Added to Task Board",
            color=color_map.get(priority, discord.Color.blue()),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Task", value=name, inline=False)
        embed.add_field(name="Priority", value=priority, inline=True)
        embed.add_field(name="Assigned To", value=assigned_to, inline=True)
        embed.add_field(name="Status", value="To-Do", inline=True)
        embed.add_field(name="Trace ID", value=trace_id, inline=False)
        embed.set_footer(text="View in Notion Task Board")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log to engine
        discord_msg = await log_to_engine(
            bot, trace_id, f"Task created: {name}",
            ["TaskManager"], ["Task Board"],
            f"Priority: {priority}, Assigned: {assigned_to}",
            success=True
        )
        await create_trace_log(
            trace_id, "Create task", ["TaskManager"], ["Task Board"], True,
            discord_link=discord_msg.jump_url if discord_msg else ""
        )
    else:
        await interaction.followup.send(
            f"❌ Failed to create task. Check #the-scream for details.\nTrace: {trace_id}",
            ephemeral=True
        )
        await log_to_scream(bot, "TASK_CREATE_FAILED", f"Failed to create: {name}", f"Trace: {trace_id}")


# =============================================================================
# AGENT MESH - DISCORD COMMANDS
# =============================================================================
import aiohttp

MINDBRIDGE_HTTP_URL = os.getenv("MINDBRIDGE_HTTP_URL", "http://localhost:3001")
MINDBRIDGE_HTTP_TOKEN = os.getenv("MINDBRIDGE_HTTP_TOKEN", "")

async def mindbridge_api(method: str, endpoint: str, data: dict = None) -> dict:
    """Call MindBridge HTTP API."""
    url = f"{MINDBRIDGE_HTTP_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if MINDBRIDGE_HTTP_TOKEN:
        headers["Authorization"] = f"Bearer {MINDBRIDGE_HTTP_TOKEN}"
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return {"status": resp.status, "data": await resp.json()}
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return {"status": resp.status, "data": await resp.json()}


@bot.tree.command(name="vessel", description="Manage Agent Mesh vessels")
@app_commands.describe(
    action="Action to perform",
    vessel_id="Vessel identifier (e.g., vessel-alpha)",
    base_url="Base URL of the vessel",
    capabilities="Comma-separated capabilities (e.g., mcp,discord)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="register", value="register"),
        app_commands.Choice(name="list", value="list"),
    ]
)
async def vessel(
    interaction: discord.Interaction,
    action: str,
    vessel_id: str = None,
    base_url: str = None,
    capabilities: str = ""
):
    """Manage Agent Mesh vessels via MindBridge."""
    await interaction.response.defer(ephemeral=True)
    trace_id = generate_trace_id()
    
    try:
        if action == "list":
            result = await mindbridge_api("GET", "/vessels")
            if result["status"] == 200 and result["data"].get("success"):
                vessels = result["data"]["vessels"]
                if not vessels:
                    await interaction.followup.send("No vessels registered.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="🚢 Registered Vessels",
                    description=f"Found {len(vessels)} vessel(s)",
                    color=discord.Color.blue()
                )
                for v in vessels:
                    caps = ", ".join(v.get("capabilities", [])) or "None"
                    embed.add_field(
                        name=v["vesselId"],
                        value=f"URL: {v['baseUrl']}\nCapabilities: {caps}",
                        inline=False
                    )
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to list vessels: {result['data'].get('error', 'Unknown error')}",
                    ephemeral=True
                )
        
        elif action == "register":
            if not vessel_id or not base_url:
                await interaction.followup.send(
                    "❌ vessel_id and base_url are required for registration.",
                    ephemeral=True
                )
                return
            
            caps = [c.strip() for c in capabilities.split(",") if c.strip()]
            result = await mindbridge_api("POST", "/vessels", {
                "vesselId": vessel_id,
                "baseUrl": base_url,
                "capabilities": caps
            })
            
            if result["status"] == 201 and result["data"].get("success"):
                v = result["data"]["vessel"]
                embed = discord.Embed(
                    title="✅ Vessel Registered",
                    description=f"Successfully registered **{v['vesselId']}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Base URL", value=v["baseUrl"], inline=False)
                embed.add_field(name="Capabilities", value=", ".join(v.get("capabilities", [])) or "None", inline=False)
                embed.add_field(name="Endpoint", value=v["migrationEndpointPath"], inline=False)
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to register vessel: {result['data'].get('error', 'Unknown error')}",
                    ephemeral=True
                )
    
    except Exception as e:
        logger.error(f"Vessel command error: {e}")
        await interaction.followup.send(
            f"❌ Error: {str(e)[:200]}\nTrace: {trace_id}",
            ephemeral=True
        )


@bot.tree.command(name="migrate", description="Manage Agent Mesh migrations")
@app_commands.describe(
    action="Action to perform",
    agent_id="Agent to migrate (e.g., calyx)",
    source="Source vessel ID",
    target="Target vessel ID",
    migration_id="Migration ID (for dispatch)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="prepare", value="prepare"),
        app_commands.Choice(name="dispatch", value="dispatch"),
        app_commands.Choice(name="list", value="list"),
    ]
)
async def migrate(
    interaction: discord.Interaction,
    action: str,
    agent_id: str = None,
    source: str = None,
    target: str = None,
    migration_id: str = None
):
    """Manage Agent Mesh migrations via MindBridge."""
    await interaction.response.defer(ephemeral=True)
    trace_id = generate_trace_id()
    
    try:
        if action == "list":
            result = await mindbridge_api("GET", "/migrations")
            if result["status"] == 200 and result["data"].get("success"):
                migrations = result["data"]["migrations"]
                if not migrations:
                    await interaction.followup.send("No migrations found.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="📦 Migrations",
                    description=f"Found {len(migrations)} migration(s)",
                    color=discord.Color.blue()
                )
                for m in migrations[:5]:  # Show max 5
                    status_emoji = {"prepared": "📋", "dispatched": "🚀", "completed": "✅", "failed": "❌"}.get(m["status"], "❓")
                    embed.add_field(
                        name=f"{status_emoji} {m['migrationId'][:8]}...",
                        value=f"Agent: {m['agentId']}\n{source} → {target}\nStatus: {m['status']}",
                        inline=True
                    )
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to list migrations: {result['data'].get('error', 'Unknown error')}",
                    ephemeral=True
                )
        
        elif action == "prepare":
            if not agent_id or not source or not target:
                await interaction.followup.send(
                    "❌ agent_id, source, and target are required.",
                    ephemeral=True
                )
                return
            
            result = await mindbridge_api("POST", "/migrations", {
                "agentId": agent_id,
                "sourceVesselId": source,
                "targetVesselId": target,
                "state": {"requestedBy": interaction.user.name, "traceId": trace_id},
                "ttlSeconds": 3600
            })
            
            if result["status"] == 201 and result["data"].get("success"):
                m = result["data"]["migration"]
                embed = discord.Embed(
                    title="📦 Migration Prepared",
                    description=f"Ready to migrate **{m['agentId']}**",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Migration ID", value=m["migrationId"], inline=False)
                embed.add_field(name="Source", value=m["sourceVesselId"], inline=True)
                embed.add_field(name="Target", value=m["targetVesselId"], inline=True)
                embed.add_field(name="Expires", value=m["expiresAt"][:19].replace("T", " "), inline=False)
                embed.add_field(name="Next Step", value=f"`/migrate action:dispatch migration_id:{m['migrationId']}`", inline=False)
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to prepare migration: {result['data'].get('error', 'Unknown error')}",
                    ephemeral=True
                )
        
        elif action == "dispatch":
            if not migration_id:
                await interaction.followup.send(
                    "❌ migration_id is required for dispatch.",
                    ephemeral=True
                )
                return
            
            result = await mindbridge_api("POST", "/migrations/dispatch", {
                "migrationId": migration_id
            })
            
            if result["status"] == 200 and result["data"].get("success"):
                r = result["data"]["result"]
                embed = discord.Embed(
                    title="🚀 Migration Dispatched",
                    description=f"Migration **{migration_id[:8]}...** sent",
                    color=discord.Color.green() if r["status"] == "completed" else discord.Color.orange()
                )
                embed.add_field(name="Status", value=r["status"], inline=True)
                embed.add_field(name="Target URL", value=r["targetUrl"][:50] + "...", inline=False)
                if r.get("announcements"):
                    embed.add_field(name="Notifications", value=f"{len(r['announcements'])} sent", inline=True)
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to dispatch: {result['data'].get('error', 'Unknown error')}",
                    ephemeral=True
                )
    
    except Exception as e:
        logger.error(f"Migrate command error: {e}")
        await interaction.followup.send(
            f"❌ Error: {str(e)[:200]}\nTrace: {trace_id}",
            ephemeral=True
        )


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================
class ConversationMemory:
    """Simple in-memory conversation store with Notion persistence."""
    
    def __init__(self, max_history=10):
        self.conversations = {}  # user_id -> list of messages
        self.max_history = max_history
    
    def get_history(self, user_id: str) -> list:
        """Get conversation history for a user."""
        return self.conversations.get(user_id, [])
    
    def add_message(self, user_id: str, role: str, content: str):
        """Add a message to user's history."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        self.conversations[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Trim old messages
        if len(self.conversations[user_id]) > self.max_history:
            self.conversations[user_id] = self.conversations[user_id][-self.max_history:]
    
    def clear_history(self, user_id: str):
        """Clear conversation history."""
        self.conversations.pop(user_id, None)
    
    def format_for_llm(self, user_id: str) -> list:
        """Format history for LLM API (OpenAI/MindBridge format)."""
        history = self.get_history(user_id)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]


# Global conversation memory
conversation_memory = ConversationMemory(max_history=20)


async def save_conversation_to_notion(user_id: str, user_name: str, summary: str):
    """Save conversation summary to Notion Memory Archive."""
    try:
        history = conversation_memory.get_history(user_id)
        if not history:
            return
        
        # Create a memory entry
        memory_content = f"Conversation with {user_name}\n\nSummary: {summary}\n\n"
        memory_content += f"Messages: {len(history)}"
        
        notion.pages.create(
            parent={"database_id": NOTION_MEMORY_ARCHIVE_ID},
            properties={
                "Memory ID": {"title": [{"text": {"content": f"CONV-{user_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"}}]},
                "Type": {"select": {"name": "Conversation"}},
                "Consent Status": {"select": {"name": "Explicit"}},
                "Created Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Last Accessed": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Access Count": {"number": 1},
                "Retention Policy": {"select": {"name": "30 Days"}},
                "Content Preview": {"rich_text": [{"text": {"content": summary[:500]}}]},
            }
        )
    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")


# =============================================================================
# LLM CHAT COMMANDS
# =============================================================================
@bot.tree.command(name="ask", description="Ask an AI assistant (Claude, GPT, etc.)")
@app_commands.describe(
    question="Your question or prompt",
    provider="Which AI to use (default: auto)",
    model="Specific model (optional)",
    context="Include conversation history?"
)
@app_commands.choices(
    provider=[
        app_commands.Choice(name="Auto", value="auto"),
        app_commands.Choice(name="Claude", value="anthropic"),
        app_commands.Choice(name="GPT-4", value="openai"),
        app_commands.Choice(name="GPT-3.5", value="openai-gpt3"),
        app_commands.Choice(name="Local (Ollama)", value="ollama"),
    ],
    context=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no"),
    ]
)
async def ask(
    interaction: discord.Interaction,
    question: str,
    provider: str = "auto",
    model: str = "",
    context: str = "yes"
):
    """Ask an AI assistant via MindBridge."""
    await interaction.response.defer(ephemeral=False, thinking=True)
    trace_id = generate_trace_id()
    user_id = str(interaction.user.id)
    
    try:
        # Build message history
        messages = []
        if context == "yes":
            history = conversation_memory.format_for_llm(user_id)
            # Add system prompt if no history
            if not history:
                messages.append({
                    "role": "system",
                    "content": "You are Calyx, a helpful AI assistant. Be concise but thorough."
                })
            else:
                messages.extend(history)
        else:
            messages.append({
                "role": "system",
                "content": "You are Calyx, a helpful AI assistant. Be concise but thorough."
            })
        
        # Add user question
        messages.append({"role": "user", "content": question})
        
        # Determine model based on provider
        model_map = {
            "auto": "claude-3-sonnet-20240229",
            "anthropic": "claude-3-sonnet-20240229",
            "openai": "gpt-4",
            "openai-gpt3": "gpt-3.5-turbo",
            "ollama": "llama2"
        }
        selected_model = model if model else model_map.get(provider, "claude-3-sonnet-20240229")
        
        # Call MindBridge
        result = await mindbridge_api("POST", "/chat", {
            "provider": provider if provider != "auto" else "anthropic",
            "model": selected_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        })
        
        if result["status"] == 200 and result["data"].get("content"):
            response_text = result["data"]["content"]
            
            # Store in conversation memory
            conversation_memory.add_message(user_id, "user", question)
            conversation_memory.add_message(user_id, "assistant", response_text)
            
            # Create embed response
            embed = discord.Embed(
                title="🤖 AI Response",
                description=response_text[:4000],
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Provider", value=provider.capitalize(), inline=True)
            embed.add_field(name="Model", value=selected_model, inline=True)
            if context == "yes":
                history_len = len(conversation_memory.get_history(user_id)) // 2
                embed.add_field(name="Context", value=f"{history_len} exchanges", inline=True)
            embed.set_footer(text=f"Trace: {trace_id} • /ask to continue")
            
            await interaction.followup.send(embed=embed)
            
            # Log to engine
            await log_to_engine(
                bot, trace_id, f"AI Chat: {question[:50]}...",
                ["LLM", provider.capitalize()], ["MindBridge"],
                f"Response: {response_text[:100]}...",
                success=True
            )
            
        else:
            error_msg = result["data"].get("error", "Unknown error")
            await interaction.followup.send(
                f"❌ AI request failed: {error_msg}\nTrace: {trace_id}",
                ephemeral=True
            )
            await log_to_scream(bot, "LLM_REQUEST_FAILED", error_msg, f"Trace: {trace_id}")
    
    except Exception as e:
        logger.error(f"Ask command error: {e}")
        await interaction.followup.send(
            f"❌ Error: {str(e)[:200]}\nTrace: {trace_id}",
            ephemeral=True
        )
        await log_to_scream(bot, "ASK_COMMAND_ERROR", str(e)[:200], f"Trace: {trace_id}")


@bot.tree.command(name="forget", description="Clear your conversation history with the AI")
async def forget(interaction: discord.Interaction):
    """Clear conversation history."""
    user_id = str(interaction.user.id)
    conversation_memory.clear_history(user_id)
    
    embed = discord.Embed(
        title="🧹 Memory Cleared",
        description="Your conversation history has been erased.",
        color=discord.Color.green()
    )
    embed.set_footer(text="Start fresh with /ask")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="think", description="Have the AI think step-by-step (reasoning mode)")
@app_commands.describe(
    problem="The problem to solve or question to analyze",
    depth="How deep to think (brief/thorough/deep)"
)
@app_commands.choices(
    depth=[
        app_commands.Choice(name="Brief", value="low"),
        app_commands.Choice(name="Thorough", value="medium"),
        app_commands.Choice(name="Deep Analysis", value="high"),
    ]
)
async def think(
    interaction: discord.Interaction,
    problem: str,
    depth: str = "medium"
):
    """Use reasoning-optimized models for complex problems."""
    await interaction.response.defer(ephemeral=False, thinking=True)
    trace_id = generate_trace_id()
    user_id = str(interaction.user.id)
    
    try:
        # Use reasoning model
        messages = [
            {
                "role": "system",
                "content": "You are an analytical AI. Think step-by-step and show your reasoning."
            },
            {"role": "user", "content": f"Please think through this carefully:\n\n{problem}"}
        ]
        
        result = await mindbridge_api("POST", "/chat", {
            "provider": "anthropic",
            "model": "claude-3-opus-20240229",  # Best reasoning model
            "messages": messages,
            "temperature": 0.3,  # Lower for more focused reasoning
            "max_tokens": 4000,
            "reasoning_effort": depth
        })
        
        if result["status"] == 200 and result["data"].get("content"):
            response_text = result["data"]["content"]
            
            # Store in memory
            conversation_memory.add_message(user_id, "user", f"[Think] {problem}")
            conversation_memory.add_message(user_id, "assistant", response_text)
            
            # Split long responses
            if len(response_text) > 4000:
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                embed = discord.Embed(
                    title="🧠 Deep Analysis (Part 1)",
                    description=parts[0],
                    color=discord.Color.purple()
                )
                embed.add_field(name="Depth", value=depth.capitalize(), inline=True)
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed)
                
                for i, part in enumerate(parts[1:], 2):
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title=f"🧠 Part {i}",
                            description=part,
                            color=discord.Color.purple()
                        )
                    )
            else:
                embed = discord.Embed(
                    title="🧠 Analysis",
                    description=response_text,
                    color=discord.Color.purple()
                )
                embed.add_field(name="Depth", value=depth.capitalize(), inline=True)
                embed.add_field(name="Model", value="Claude 3 Opus", inline=True)
                embed.set_footer(text=f"Trace: {trace_id}")
                await interaction.followup.send(embed=embed)
        else:
            error_msg = result["data"].get("error", "Unknown error")
            await interaction.followup.send(f"❌ Analysis failed: {error_msg}", ephemeral=True)
    
    except Exception as e:
        logger.error(f"Think command error: {e}")
        await interaction.followup.send(f"❌ Error: {str(e)[:200]}", ephemeral=True)


# =============================================================================
# AUTO-RESPOND MODE (for specific channels)
# =============================================================================
AUTO_RESPOND_CHANNELS = set()  # Channel IDs where bot auto-responds

@bot.tree.command(name="autorespond", description="Toggle AI auto-respond in this channel")
@app_commands.describe(mode="Enable or disable")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Enable", value="on"),
        app_commands.Choice(name="Disable", value="off"),
        app_commands.Choice(name="Status", value="status"),
    ]
)
async def autorespond(interaction: discord.Interaction, mode: str):
    """Toggle automatic AI responses in the current channel."""
    channel_id = interaction.channel_id
    
    if mode == "on":
        AUTO_RESPOND_CHANNELS.add(channel_id)
        embed = discord.Embed(
            title="🤖 Auto-Respond Enabled",
            description="I'll automatically respond to messages in this channel.",
            color=discord.Color.green()
        )
        embed.add_field(name="Trigger", value="Any message", inline=True)
        embed.add_field(name="Context", value="Per-user memory", inline=True)
        embed.set_footer(text="Use /autorespond mode:disable to turn off")
        await interaction.response.send_message(embed=embed)
    
    elif mode == "off":
        AUTO_RESPOND_CHANNELS.discard(channel_id)
        await interaction.response.send_message(
            "🤖 Auto-respond disabled for this channel.",
            ephemeral=True
        )
    
    else:  # status
        status = "enabled" if channel_id in AUTO_RESPOND_CHANNELS else "disabled"
        await interaction.response.send_message(
            f"Auto-respond is **{status}** in this channel.",
            ephemeral=True
        )


@bot.event
async def on_message(message):
    """Handle auto-respond messages."""
    # Skip if not in auto-respond channel
    if message.channel.id not in AUTO_RESPOND_CHANNELS:
        await bot.process_commands(message)
        return
    
    # Skip bot messages and commands
    if message.author.bot or message.content.startswith('/'):
        await bot.process_commands(message)
        return
    
    # Skip if it's a command invocation
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return
    
    # Auto-respond with AI
    try:
        user_id = str(message.author.id)
        
        # Build context
        history = conversation_memory.format_for_llm(user_id)
        messages = [{"role": "system", "content": "You are Calyx, helpful and concise."}]
        if history:
            messages.extend(history[-6:])  # Last 3 exchanges
        messages.append({"role": "user", "content": message.content})
        
        # Quick async call to MindBridge
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if MINDBRIDGE_HTTP_TOKEN:
                headers["Authorization"] = f"Bearer {MINDBRIDGE_HTTP_TOKEN}"
            
            async with session.post(
                f"{MINDBRIDGE_HTTP_URL}/chat",
                headers=headers,
                json={
                    "provider": "anthropic",
                    "model": "claude-3-haiku-20240307",  # Fast model for chat
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("content"):
                        response_text = data["content"]
                        conversation_memory.add_message(user_id, "user", message.content)
                        conversation_memory.add_message(user_id, "assistant", response_text)
                        await message.reply(response_text[:2000])
    
    except Exception as e:
        logger.error(f"Auto-respond error: {e}")
    
    await bot.process_commands(message)


# =============================================================================
# SIGNAL HANDLING FOR SYSTEMD
# =============================================================================
import signal
import sys

shutdown_event = asyncio.Event()

def handle_signal(sig, frame):
    """Handle shutdown signals gracefully for systemd."""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()
    
    # Close the bot
    async def shutdown():
        try:
            if health_server:
                await health_server.stop()
                logger.info("Health server stopped")
            await bot.close()
            logger.info("Bot connection closed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    # Run shutdown
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(shutdown())
        else:
            loop.run_until_complete(shutdown())
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    finally:
        sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


# =============================================================================
# RUN BOT
# =============================================================================
if __name__ == "__main__":
    if not TOKEN:
        logger.error("ERROR: DISCORD_TOKEN not found in .env")
        exit(1)
    if not NOTION_TOKEN:
        logger.warning("WARNING: NOTION_TOKEN configured. Notion features will be disabled.")
    
    logger.info("Starting Calyx bot...")
    logger.info("PID: %s", os.getpid())
    logger.info("Press Ctrl+C or send SIGTERM to stop")
    
    try:
        bot.run(TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        handle_signal(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
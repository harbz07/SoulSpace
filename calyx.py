import asyncio
import json
import os
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

# Google OAuth imports
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError

from dotenv import load_dotenv
load_dotenv()

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
# The Glass Journal - hardcoded per specification
JOURNAL_DB_ID = "3978eb18cdc04c0590484b9051ea6571"

# Initialize Notion client
notion = None

if NOTION_TOKEN:
    try:
        notion = NotionClient(auth=NOTION_TOKEN)
        notion.users.me()
        print("Notion auth verified")
    except Exception as e:
        print("Notion auth failed:", e)
        notion = None
else:
    print("NOTION_TOKEN not found")

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OAUTH_REDIRECT_PORT = 9090
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}/callback"

# Token storage directory
TOKEN_DIR = os.path.join(os.path.dirname(__file__), "tokens")
os.makedirs(TOKEN_DIR, exist_ok=True)

# Google OAuth scopes for different services
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

# Store for pending OAuth flows (user_id -> Flow)
pending_oauth_flows = {}

# Global state
OPERATIONS_PAUSED = False
last_processed_id = None

# Channel type mapping
CHANNEL_TYPES = {}


def init_channel_types():
    """Initialize channel type mapping after bot is ready."""
    global CHANNEL_TYPES
    CHANNEL_TYPES = {
        CHANNEL_THE_WELL: "the-well",
        CHANNEL_ENGINE_LOGS: "engine-logs",
        CHANNEL_THE_SCREAM: "the-scream",
        CHANNEL_THE_MIRROR: "the-mirror",
        CHANNEL_THE_COUNSEL: "the-counsel",
    }


def get_channel_context(channel_id: str) -> str:
    """Identify which channel type a message is from."""
    return CHANNEL_TYPES.get(str(channel_id), "unknown")


def generate_trace_id() -> str:
    """Generate a unique trace ID."""
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
    """Post structured trace log to #engine-logs channel."""
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
```"""

    message = await channel.send(log_message)
    return message


async def log_to_scream(
    bot: commands.Bot, error_type: str, error_msg: str, context: str = ""
):
    """Post error to #the-scream channel."""
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
    """Create entry in Notion Trace Log Index database."""
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
        print(f"Notion API Error (create_trace_log): {e}")
        return None


async def update_agent_health(
    agent_name: str,
    status: str = None,
    increment_execution: bool = False,
    increment_error: bool = False,
    error_message: str = None,
    auth_status: str = None,
):
    """Update Agent Health Monitor in Notion."""
    if not notion or not NOTION_AGENT_HEALTH_ID:
        return None

    try:
        # Query for existing agent entry
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
            # Update existing entry
            page_id = response["results"][0]["id"]
            current_props = response["results"][0]["properties"]

            if increment_execution:
                current_count = (
                    current_props.get("Execution Count", {}).get("number", 0) or 0
                )
                properties["Execution Count"] = {"number": current_count + 1}

            if increment_error:
                current_errors = (
                    current_props.get("Error Count", {}).get("number", 0) or 0
                )
                properties["Error Count"] = {"number": current_errors + 1}

            notion.pages.update(page_id=page_id, properties=properties)
        else:
            # Create new entry
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
        print(f"Notion API Error (update_agent_health): {e}")
        return None


async def query_memory_archive(memory_id: str):
    """Query Memory Archive for a specific memory."""
    if not notion or not NOTION_MEMORY_ARCHIVE_ID:
        return None

    try:
        response = notion.databases.query(
            database_id=NOTION_MEMORY_ARCHIVE_ID,
            filter={"property": "Memory ID", "title": {"equals": memory_id}},
        )
        return response["results"][0] if response["results"] else None
    except APIResponseError as e:
        print(f"Notion API Error (query_memory_archive): {e}")
        return None


async def delete_memory(page_id: str):
    """Archive (delete) a memory from Notion."""
    if not notion:
        return False

    try:
        notion.pages.update(page_id=page_id, archived=True)
        return True
    except APIResponseError as e:
        print(f"Notion API Error (delete_memory): {e}")
        return False


async def add_to_knowledge_base(
    title: str, category: str, content: str, source: str = "Harvey Input"
):
    """Add entry to Knowledge Base."""
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
        print(f"Notion API Error (add_to_knowledge_base): {e}")
        return None


async def query_all_agent_health():
    """Query all agents from Agent Health Monitor."""
    if not notion or not NOTION_AGENT_HEALTH_ID:
        return []

    try:
        response = notion.databases.query(database_id=NOTION_AGENT_HEALTH_ID)
        return response["results"]
    except APIResponseError as e:
        print(f"Notion API Error (query_all_agent_health): {e}")
        return []


async def set_all_agents_status(status: str):
    """Set all agents to a specific status."""
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
        print(f"Notion API Error (set_all_agents_status): {e}")
        return False


async def query_trace_by_id(trace_id: str):
    """Query Trace Log Index by trace ID."""
    if not notion or not NOTION_TRACE_LOG_ID:
        return None

    try:
        response = notion.databases.query(
            database_id=NOTION_TRACE_LOG_ID,
            filter={"property": "Trace ID", "title": {"equals": trace_id}},
        )
        return response["results"][0] if response["results"] else None
    except APIResponseError as e:
        print(f"Notion API Error (query_trace_by_id): {e}")
        return None


# =============================================================================
# GOOGLE OAUTH HELPER FUNCTIONS
# =============================================================================


def create_oauth_flow(service: str) -> Flow:
    """Create a Google OAuth flow for the specified service."""
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
    """Get the file path for a service's token file."""
    return os.path.join(TOKEN_DIR, f"{service.lower()}_token.json")


async def store_oauth_tokens(service: str, credentials: Credentials) -> bool:
    """Store OAuth tokens to local JSON file."""
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
        print(f"Stored OAuth token for {service} at {token_path}")
        return True
    except Exception as e:
        print(f"Error storing token to file: {e}")
        return False


async def get_oauth_tokens(service: str) -> Credentials | None:
    """Retrieve OAuth tokens from local JSON file."""
    token_path = get_token_path(service)

    if not os.path.exists(token_path):
        print(f"No token file found for {service}")
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

        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            print(f"Refreshing expired token for {service}")
            credentials.refresh(Request())
            await store_oauth_tokens(service, credentials)

        return credentials
    except Exception as e:
        print(f"Error retrieving OAuth tokens: {e}")
        return None


def list_stored_tokens() -> list:
    """List all stored token files."""
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
    """Run a temporary local server to receive the OAuth callback."""
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
        print(f"OAuth callback server started on port {OAUTH_REDIRECT_PORT}")

        # Wait for callback or timeout
        try:
            await asyncio.wait_for(auth_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print("OAuth callback timed out")
            return None

        return auth_code
    finally:
        await runner.cleanup()


async def export_all_databases():
    """Export all Notion databases to JSON."""
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
        print(f"Synced slash commands for {self.user}")


bot = CalyxBot()


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
        label="Confirm Purge", style=discord.ButtonStyle.danger, emoji="\U0001f5d1"
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
                content=f"Memory **{self.memory_id}** has been permanently purged.",
                view=None,
            )
        else:
            await log_to_scream(
                bot, "PURGE_FAILED", f"Failed to purge memory {self.memory_id}"
            )
            await interaction.response.edit_message(
                content=f"Failed to purge memory **{self.memory_id}**. Check #the-scream for details.",
                view=None,
            )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=f"Purge cancelled. Memory **{self.memory_id}** retained.", view=None
        )
        self.stop()


# =============================================================================
# EVENT HANDLERS
# =============================================================================


@bot.event
async def on_ready():
    init_channel_types()
    print(f"Calyx Online: {bot.user}")
    print(f"Operations Paused: {OPERATIONS_PAUSED}")

    # Update Calyx agent health
    await update_agent_health("Calyx", status="Active", increment_execution=True)

    # Start the Glass Journal polling task
    if notion and not poll_glass_journal.is_running():
        poll_glass_journal.start()
        print("Broadcast Protocol Active - polling The Glass Journal")

    # Post status to #the-mirror if configured
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

    # Skip if operations are paused (except for commands)
    if OPERATIONS_PAUSED and not message.content.startswith("!"):
        return

    channel_type = get_channel_context(str(message.channel.id))

    # Channel-specific behavior
    if channel_type == "the-well":
        # Primary interaction channel - bot can respond naturally here
        # For now, just process commands
        pass
    elif channel_type == "the-counsel":
        # Meta-discussion - bot listens but doesn't auto-respond
        pass

    await bot.process_commands(message)


@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Log traces for messages in #the-well
    if message.channel.name == "the-well":
        trace_id = f"TRACE-{message.id}"
        await log_trace(
            trace_id=trace_id,
            request_summary=message.content[:200],
            agent_chain="tinyNature → Calyx",
            data_sources=["Knowledge Base"],
            discord_link=message.jump_url,
            success=True
        )
    
    # Log technical activity in #engine-logs
    elif message.channel.name == "engine-logs":
        # Parse structured logs here if needed
        pass

# =============================================================================
# BROADCAST PULSE (Notion Journal Polling)
# =============================================================================

@tasks.loop(minutes=5)
async def poll_glass_journal():
    """Poll The Glass Journal database for new entries and broadcast to Discord."""
    global last_processed_id
    
    # Check if notion is configured
    if not notion:
        return
    
    # Check if channel is configured
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
                # Safely extract title
                title_array = latest_page["properties"]["Name"]["title"]
                if title_array and len(title_array) > 0:
                    title = title_array[0]["plain_text"]
                else:
                    title = "Untitled"
                
                url = f"https://www.notion.so/{page_id.replace('-', '')}"
                
                message = f"**[SYSTEM LOG]** New entry detected in The Glass Journal:\n**{title}**\nView: {url}"
                await channel.send(message)
                last_processed_id = page_id
    except Exception as e:
        print(f"Broadcast Error ({type(e).__name__}): {e}")

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

    # Log to engine
    await log_to_engine(
        bot,
        trace_id,
        f"Auth request: {service}",
        ["AuthManager"],
        ["Agent Health"],
        f"Initiated auth flow for {service}",
    )

    # Handle Notion (already configured via token)
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
        embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Handle Google services (Gmail, Calendar)
    if service_lower in ["gmail", "calendar"]:
        # Check if Google OAuth is configured
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            await interaction.response.send_message(
                "Google OAuth not configured. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to .env",
                ephemeral=True,
            )
            return

        # Check for existing valid tokens
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
            embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
            embed.set_footer(text="Run /auth again to re-authenticate if needed.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Start OAuth flow
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Create OAuth flow
            flow = create_oauth_flow(service_lower)
            auth_url, _ = flow.authorization_url(
                access_type="offline", include_granted_scopes="true", prompt="consent"
            )

            # Store flow for this user
            pending_oauth_flows[interaction.user.id] = {
                "flow": flow,
                "service": service_lower,
                "trace_id": trace_id,
            }

            # Send auth URL to user
            embed = discord.Embed(
                title=f"Authenticate {service.capitalize()}",
                description="Click the link below to authorize access.\n\n"
                "**Important:** After authorizing, you'll be redirected to localhost. "
                "Make sure the bot is running locally to receive the callback.",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Authorization URL",
                value=f"[Click here to authorize]({auth_url})",
                inline=False,
            )
            embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
            embed.add_field(name="Timeout", value="2 minutes", inline=True)
            embed.set_footer(text="Waiting for authorization...")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Start callback server and wait for auth code
            auth_code = await run_oauth_callback_server(flow, timeout=120)

            if auth_code:
                # Exchange code for tokens
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials

                # Store tokens in Notion
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
                        name="Trace ID", value=f"`{trace_id}`", inline=True
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
                    "Authorization timed out. Please try `/auth` again.", ephemeral=True
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
                f"OAuth error: {str(e)[:200]}\n\nCheck #the-scream for details.",
                ephemeral=True,
            )

        finally:
            # Clean up pending flow
            pending_oauth_flows.pop(interaction.user.id, None)

        return

    # Unknown service
    await update_agent_health(
        f"{service.capitalize()}Service", auth_status="N/A", increment_execution=True
    )
    embed = discord.Embed(
        title=f"Authentication: {service.capitalize()}",
        description=f"Auth flow for {service} is not yet implemented.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
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
    trace_id = generate_trace_id()

    # Store in Knowledge Base
    result = await add_to_knowledge_base(
        title=f"Preference: {parameter}",
        category="Personal",
        content=f"{parameter} = {value}\n\nSet by Harvey on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        source="Harvey Input",
    )

    success = result is not None

    # Log to engine
    discord_msg = await log_to_engine(
        bot,
        trace_id,
        f"Soul adjustment: {parameter} -> {value}",
        ["SoulManager", "KnowledgeBase"],
        ["Knowledge Base"],
        "Success - Preference updated" if success else "Failed - Could not update",
        success=success,
    )

    # Create trace log
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
            description=f"**{parameter}** has been set to **{value}**",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
        embed.set_footer(text="Preference stored in Knowledge Base.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await log_to_scream(
            bot,
            "SOUL_UPDATE_FAILED",
            f"Could not update {parameter} to {value}",
            f"Trace: {trace_id}",
        )
        await interaction.response.send_message(
            f"Failed to update soul parameter. Check #the-scream for details.\nTrace: `{trace_id}`",
            ephemeral=True,
        )


@bot.tree.command(name="trace", description="Get raw logs for specific trace ID")
@app_commands.describe(trace_id="The trace ID to look up (e.g., TRC-ABC12345)")
async def trace(interaction: discord.Interaction, trace_id: str):
    # Query Notion Trace Log
    trace_data = await query_trace_by_id(trace_id)

    if trace_data:
        props = trace_data["properties"]

        # Extract data from Notion properties
        request = (
            props.get("Request Summary", {})
            .get("rich_text", [{}])[0]
            .get("text", {})
            .get("content", "N/A")
        )
        agents = (
            props.get("Agent Chain", {})
            .get("rich_text", [{}])[0]
            .get("text", {})
            .get("content", "N/A")
        )
        sources = [
            s["name"]
            for s in props.get("Data Sources Used", {}).get("multi_select", [])
        ]
        success = props.get("Success", {}).get("checkbox", False)
        timestamp = props.get("Timestamp", {}).get("date", {}).get("start", "N/A")
        discord_link = props.get("Discord Link", {}).get("url", "")

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
            f"No trace found for ID: `{trace_id}`\n\n"
            "Trace IDs are formatted as `TRC-XXXXXXXX`. "
            "Check #engine-logs for recent traces.",
            ephemeral=True,
        )


@bot.tree.command(
    name="status", description="Show all agent health + last execution times"
)
async def status(interaction: discord.Interaction):
    agents = await query_all_agent_health()

    embed = discord.Embed(
        title="Vessel System Status",
        color=discord.Color.green()
        if not OPERATIONS_PAUSED
        else discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )

    # Global status
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

    # Agent statuses
    if agents:
        for agent in agents[:10]:  # Limit to 10 agents for embed
            props = agent["properties"]
            name = (
                props.get("Agent Name", {})
                .get("title", [{}])[0]
                .get("text", {})
                .get("content", "Unknown")
            )
            agent_status = (
                props.get("Status", {}).get("select", {}).get("name", "Unknown")
            )
            exec_count = props.get("Execution Count", {}).get("number", 0)
            error_count = props.get("Error Count", {}).get("number", 0)
            auth = props.get("Auth Status", {}).get("select", {}).get("name", "N/A")

            status_emoji = {
                "Active": "\U00002705",
                "Paused": "\U000023f8",
                "Error": "\U0000274c",
                "Disabled": "\U000026d4",
            }.get(agent_status, "\U00002753")

            embed.add_field(
                name=f"{status_emoji} {name}",
                value=f"Status: {agent_status}\nRuns: {exec_count} | Errors: {error_count}\nAuth: {auth}",
                inline=True,
            )
    else:
        embed.add_field(
            name="Agents",
            value="No agents registered in Agent Health Monitor.\nRun commands to auto-register agents.",
            inline=False,
        )

    embed.set_footer(text="Use /pause to suspend operations, /resume to continue.")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="pause", description="Temporarily suspend all automated triggers"
)
async def pause(interaction: discord.Interaction):
    global OPERATIONS_PAUSED

    trace_id = generate_trace_id()
    OPERATIONS_PAUSED = True

    # Update all agents to Paused
    await set_all_agents_status("Paused")

    # Log to engine
    await log_to_engine(
        bot,
        trace_id,
        "System pause requested",
        ["SystemController"],
        ["Agent Health"],
        "Success - All operations paused",
    )

    # Create trace log
    await create_trace_log(
        trace_id, "System pause requested", ["SystemController"], ["Agent Health"], True
    )

    embed = discord.Embed(
        title="Operations Suspended",
        description="All automated triggers are now **offline**.\n\nSlash commands remain available.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
    embed.set_footer(text="Use /resume to re-enable operations.")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="resume", description="Re-enable automated operations")
async def resume(interaction: discord.Interaction):
    global OPERATIONS_PAUSED

    trace_id = generate_trace_id()
    OPERATIONS_PAUSED = False

    # Update all agents to Active
    await set_all_agents_status("Active")

    # Log to engine
    await log_to_engine(
        bot,
        trace_id,
        "System resume requested",
        ["SystemController"],
        ["Agent Health"],
        "Success - All operations resumed",
    )

    # Create trace log
    await create_trace_log(
        trace_id,
        "System resume requested",
        ["SystemController"],
        ["Agent Health"],
        True,
    )

    embed = discord.Embed(
        title="Operations Resumed",
        description="Calyx is back in the driver's seat.\n\nAll automated triggers are now **online**.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="purge", description="Delete specific memory (requires confirmation)"
)
@app_commands.describe(memory_id="The unique ID of the memory to purge")
async def purge(interaction: discord.Interaction, memory_id: str):
    # Query Memory Archive
    memory = await query_memory_archive(memory_id)

    if not memory:
        await interaction.response.send_message(
            f"Memory **{memory_id}** not found in Memory Archive.\n\n"
            "Check the Memory ID and try again.",
            ephemeral=True,
        )
        return

    # Extract memory details for preview
    props = memory["properties"]
    mem_type = props.get("Type", {}).get("select", {}).get("name", "Unknown")
    consent = props.get("Consent Status", {}).get("select", {}).get("name", "Unknown")
    preview = (
        props.get("Content Preview", {})
        .get("rich_text", [{}])[0]
        .get("text", {})
        .get("content", "No preview available")
    )

    embed = discord.Embed(
        title=f"Confirm Purge: {memory_id}",
        description="This action is **irreversible**. The memory will be permanently deleted.",
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

    # Export all databases
    export_data = await export_all_databases()
    export_data["trace_id"] = trace_id

    # Convert to JSON
    json_str = json.dumps(export_data, indent=2, default=str)

    # Log to engine
    db_count = len([k for k, v in export_data["databases"].items() if "error" not in v])
    await log_to_engine(
        bot,
        trace_id,
        "Full data export requested",
        ["ExportManager"],
        list(export_data["databases"].keys()),
        f"Success - Exported {db_count} databases",
    )

    # Create trace log
    await create_trace_log(
        trace_id,
        "Full data export requested",
        ["ExportManager"],
        list(export_data["databases"].keys()),
        True,
    )

    # Create file
    filename = f"vessel_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file = discord.File(
        fp=__import__("io").BytesIO(json_str.encode()), filename=filename
    )

    embed = discord.Embed(
        title="Data Export Complete",
        description=f"Exported **{db_count}** databases to JSON.",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Trace ID", value=f"`{trace_id}`", inline=True)
    embed.add_field(name="File", value=filename, inline=True)

    # Summary of what was exported
    summary_lines = []
    for name, data in export_data["databases"].items():
        if "error" in data:
            summary_lines.append(f"- {name}: Error")
        else:
            summary_lines.append(f"- {name}: {data['count']} entries")

    embed.add_field(name="Contents", value="\n".join(summary_lines), inline=False)

    await interaction.followup.send(embed=embed, file=file, ephemeral=True)


# =============================================================================
# RUN BOT
# =============================================================================

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found in .env")
        exit(1)

    if not NOTION_TOKEN:
        print("WARNING: NOTION_TOKEN not configured. Notion features will be disabled.")

    bot.run(TOKEN)

"""
Notion Integration for Calyx
Writes Discord activity to Vessel Framework databases
"""

import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from notion_client import Client

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Notion client
notion = Client(auth=os.getenv("NOTION_TOKEN"))

# Database IDs from environment variables
TASK_BOARD_ID = os.getenv("NOTION_TASK_BOARD_ID")
TRACE_LOGS_ID = os.getenv("NOTION_TRACE_LOG_ID")
AGENT_HEALTH_ID = os.getenv("NOTION_AGENT_HEALTH_ID")


async def log_trace(
    trace_id: str,
    request_summary: str,
    agent_chain: str,
    data_sources: list,
    discord_link: str,
    success: bool
):
    """
    Log a trace entry to Notion Trace Logs database
    
    Args:
        trace_id: Unique identifier for this trace
        request_summary: What Harvey asked
        agent_chain: Which agents were called (e.g., "EmailMonitor → DraftGenerator")
        data_sources: List of sources used (e.g., ["Gmail API", "Knowledge Base"])
        discord_link: URL to the message in Discord
        success: Whether the operation succeeded
    """
    try:
        notion.pages.create(
            parent={"database_id": TRACE_LOGS_ID},
            properties={
                "Trace ID": {"title": [{"text": {"content": trace_id}}]},
                "Timestamp": {
                    "date": {"start": datetime.now(timezone.utc).isoformat()}
                },
                "Request Summary": {
                    "rich_text": [{"text": {"content": request_summary}}]
                },
                "Agent Chain": {
                    "rich_text": [{"text": {"content": agent_chain}}]
                },
                "Data Sources Used": {
                    "multi_select": [{"name": source} for source in data_sources]
                },
                "Discord Link": {"url": discord_link},
                "Success": {"checkbox": success}
            }
        )
        logger.info(f"Logged trace {trace_id} to Notion")
    except Exception as e:
        logger.error(f"Failed to log trace: {e}")


async def create_task(
    task_name: str,
    status: str = "To-Do",
    priority: str = "Medium",
    assigned_to: str = "Calyx",
    trigger_source: str = "Manual",
    trace_link: str = None,
    blocker_reason: str = None
):
    """
    Create a task in Notion Task Board
    
    Args:
        task_name: Name of the task
        status: One of ["To-Do", "Executing", "Blocked", "Done", "Cancelled"]
        priority: One of ["Critical", "High", "Medium", "Low"]
        assigned_to: One of ["tinyNature", "Calyx", "Harvey", "Claude", "Other"]
        trigger_source: One of ["Manual", "TIME", "EVENT", "API"]
        trace_link: URL to Discord trace message
        blocker_reason: If blocked, why?
    """
    try:
        properties = {
            "Task": {"title": [{"text": {"content": task_name}}]},
            "Status": {"select": {"name": status}},
            "Priority": {"select": {"name": priority}},
            "Assigned To": {"select": {"name": assigned_to}},
            "Trigger Source": {"select": {"name": trigger_source}}
        }
        
        if trace_link:
            properties["Trace Link"] = {"url": trace_link}
        
        if blocker_reason:
            properties["Blocker Reason"] = {
                "rich_text": [{"text": {"content": blocker_reason}}]
            }
        
        result = notion.pages.create(
            parent={"database_id": TASK_BOARD_ID},
            properties=properties
        )
        logger.info(f"Created task: {task_name}")
        return result
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        return None


async def update_agent_health(
    agent_name: str,
    status: str,
    execution_count: int = None,
    error_count: int = None,
    last_error: str = None,
    auth_status: str = "N/A"
):
    """
    Update agent health status in Notion
    
    Args:
        agent_name: Name of the agent
        status: One of ["Active", "Paused", "Error", "Disabled"]
        execution_count: Total number of executions
        error_count: Total number of errors
        last_error: Most recent error message
        auth_status: One of ["Valid", "Expired", "Invalid", "N/A"]
    """
    try:
        # First, check if agent already exists
        results = notion.databases.query(
            database_id=AGENT_HEALTH_ID,
            filter={
                "property": "Agent Name",
                "title": {"equals": agent_name}
            }
        )
        
        properties = {
            "Agent Name": {"title": [{"text": {"content": agent_name}}]},
            "Status": {"select": {"name": status}},
            "Last Execution": {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            },
            "Auth Status": {"select": {"name": auth_status}}
        }
        
        if execution_count is not None:
            properties["Execution Count"] = {"number": execution_count}
        
        if error_count is not None:
            properties["Error Count"] = {"number": error_count}
        
        if last_error:
            properties["Last Error Message"] = {
                "rich_text": [{"text": {"content": last_error}}]
            }
        
        if results["results"]:
            # Update existing
            page_id = results["results"][0]["id"]
            notion.pages.update(page_id=page_id, properties=properties)
            logger.info(f"Updated health for {agent_name}")
        else:
            # Create new
            notion.pages.create(
                parent={"database_id": AGENT_HEALTH_ID},
                properties=properties
            )
            logger.info(f"Created health entry for {agent_name}")
    
    except Exception as e:
        logger.error(f"Failed to update agent health: {e}")


# Example usage in Discord bot:
"""
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Log trace for every message in #the-well
    if message.channel.name == "the-well":
        trace_id = f"TRACE-{message.id}"
        await log_trace(
            trace_id=trace_id,
            request_summary=message.content[:200],  # First 200 chars
            agent_chain="tinyNature → Calyx",
            data_sources=["Knowledge Base"],
            discord_link=message.jump_url,
            success=True
        )
"""

"""
Notion Integration for Calyx
Writes Discord activity to Vessel Framework databases
"""

import os
from datetime import datetime
from notion_client import Client

# Initialize Notion client
notion = Client(auth=os.getenv("NOTION_TOKEN"))

# Database IDs from Notion
TASK_BOARD_ID = "5940340de126424e801c85baf87765ea"
TRACE_LOGS_ID = "7e61b65260ad4c07ae2eb14987ddcdec"
AGENT_HEALTH_ID = "62ed0fc6c10344a7b941a271c7bf1518"


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
                    "date": {"start": datetime.utcnow().isoformat()}
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
        print(f"✅ Logged trace {trace_id} to Notion")
    except Exception as e:
        print(f"❌ Failed to log trace: {e}")


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
        
        notion.pages.create(
            parent={"database_id": TASK_BOARD_ID},
            properties=properties
        )
        print(f"✅ Created task: {task_name}")
    except Exception as e:
        print(f"❌ Failed to create task: {e}")


async def update_agent_health(
    agent_name: str,
    status: str = None,
    execution_count: int = None,
    error_count: int = None,
    last_error: str = None,
    increment_execution: bool = False,
    increment_error: bool = False,
    error_message: str = None,
    auth_status: str = None,
):
    """
    Unified implementation of update_agent_health.
    
    Update agent health status in Notion with support for both explicit counts
    and increment flags for backward compatibility.
    
    Args:
        agent_name: Name of the agent
        status: One of ["Active", "Paused", "Error", "Disabled"] (optional)
        execution_count: Total number of executions (explicit value)
        error_count: Total number of errors (explicit value)
        last_error: Most recent error message
        increment_execution: If True, increment execution count by 1
        increment_error: If True, increment error count by 1
        error_message: Alias for last_error (for backward compatibility)
        auth_status: One of ["Valid", "Expired", "Invalid", "N/A"] (optional)
    
    Returns:
        True on success, None on failure or if Notion is not configured
    """
    # Use environment variable for database ID, fallback to hardcoded
    database_id = os.getenv("NOTION_AGENT_HEALTH_ID", AGENT_HEALTH_ID)
    
    # Check if notion client is available
    if not notion or not database_id:
        return None
    
    # Handle error_message alias
    if error_message and not last_error:
        last_error = error_message
    
    try:
        # Query for existing agent entry
        results = notion.databases.query(
            database_id=database_id,
            filter={
                "property": "Agent Name",
                "title": {"equals": agent_name}
            }
        )
        
        properties = {}
        
        # Add status if provided
        if status:
            properties["Status"] = {"select": {"name": status}}
        
        # Add auth status if provided
        if auth_status:
            properties["Auth Status"] = {"select": {"name": auth_status}}
        
        # Add error message if provided
        if last_error:
            # Truncate to 2000 characters to avoid Notion API rich_text limits
            properties["Last Error Message"] = {
                "rich_text": [{"text": {"content": last_error[:2000]}}]
            }
        
        # Always update Last Execution timestamp
        properties["Last Execution"] = {
            "date": {"start": datetime.utcnow().isoformat()}
        }
        
        if results["results"]:
            # Update existing entry
            page_id = results["results"][0]["id"]
            current_props = results["results"][0]["properties"]
            
            # Handle execution count
            if increment_execution:
                current_count = (
                    current_props.get("Execution Count", {}).get("number", 0) or 0
                )
                properties["Execution Count"] = {"number": current_count + 1}
            elif execution_count is not None:
                properties["Execution Count"] = {"number": execution_count}
            
            # Handle error count
            if increment_error:
                current_errors = (
                    current_props.get("Error Count", {}).get("number", 0) or 0
                )
                properties["Error Count"] = {"number": current_errors + 1}
            elif error_count is not None:
                properties["Error Count"] = {"number": error_count}
            
            notion.pages.update(page_id=page_id, properties=properties)
            print(f"✅ Updated health for {agent_name}")
        else:
            # Create new entry
            properties["Agent Name"] = {"title": [{"text": {"content": agent_name}}]}
            
            # Set initial counts for new entry
            if increment_execution:
                properties["Execution Count"] = {"number": 1}
            elif execution_count is not None:
                properties["Execution Count"] = {"number": execution_count}
            else:
                properties["Execution Count"] = {"number": 0}
            
            if increment_error:
                properties["Error Count"] = {"number": 1}
            elif error_count is not None:
                properties["Error Count"] = {"number": error_count}
            else:
                properties["Error Count"] = {"number": 0}
            
            notion.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            print(f"✅ Created health entry for {agent_name}")
        
        return True
    
    except Exception as e:
        print(f"❌ Failed to update agent health: {e}")
        return None


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

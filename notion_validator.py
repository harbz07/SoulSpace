"""
Notion Schema Validator for Calyx
Validates Notion database schemas on startup to catch configuration issues early.
"""

import logging
from typing import Dict, List, Tuple
from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

# Expected schemas for all 5 databases
EXPECTED_SCHEMAS = {
    "task_board": {
        "Task": "title",
        "Status": "select",
        "Priority": "select",
        "Assigned To": "select",
        "Trigger Source": "select",
        "Trace Link": "url",
        "Blocker Reason": "rich_text"
    },
    "trace_log": {
        "Trace ID": "title",
        "Timestamp": "date",
        "Request Summary": "rich_text",
        "Agent Chain": "rich_text",
        "Data Sources Used": "multi_select",
        "Discord Link": "url",
        "Success": "checkbox"
    },
    "agent_health": {
        "Agent Name": "title",
        "Status": "select",
        "Last Execution": "date",
        "Execution Count": "number",
        "Error Count": "number",
        "Last Error Message": "rich_text",
        "Auth Status": "select"
    },
    "knowledge_base": {
        "Entry Title": "title",
        "Category": "select",
        "Consent Level": "select",
        "Source": "select",
        "Last Verified": "date"
    },
    "memory_archive": {
        "Memory ID": "title",
        "Type": "select",
        "Consent Status": "select",
        "Created Date": "date",
        "Last Accessed": "date",
        "Access Count": "number",
        "Retention Policy": "select",
        "Content Preview": "rich_text"
    }
}


def validate_database_schema(
    notion_client: Client,
    database_id: str,
    database_name: str,
    expected_schema: Dict[str, str]
) -> Tuple[bool, List[str]]:
    """
    Validate a single Notion database schema.
    
    Args:
        notion_client: Authenticated Notion client
        database_id: Database ID to validate
        expected_schema: Dictionary of expected property names and types
        database_name: Human-readable database name for logging
    
    Returns:
        Tuple of (is_valid, issues_list)
        - is_valid: True if no errors (warnings are OK)
        - issues_list: List of issue strings to display
    """
    issues = []
    
    if not database_id:
        issues.append(f"❌ {database_name}: Database ID not configured")
        return False, issues
    
    try:
        # Fetch database metadata
        database = notion_client.databases.retrieve(database_id=database_id)
        actual_properties = database.get("properties", {})
        
        # Track which expected properties we've checked
        checked_properties = set()
        
        # Check each expected property
        for expected_name, expected_type in expected_schema.items():
            checked_properties.add(expected_name)
            
            if expected_name in actual_properties:
                # Exact match found - check type
                actual_type = actual_properties[expected_name].get("type")
                if actual_type == expected_type:
                    # Perfect match
                    pass
                else:
                    issues.append(
                        f"❌ {database_name}: Property '{expected_name}' has wrong type "
                        f"(expected: {expected_type}, actual: {actual_type})"
                    )
            else:
                # No exact match - check for case-insensitive match
                case_insensitive_matches = [
                    prop_name for prop_name in actual_properties.keys()
                    if prop_name.lower() == expected_name.lower()
                ]
                
                if case_insensitive_matches:
                    actual_name = case_insensitive_matches[0]
                    issues.append(
                        f"⚠️  {database_name}: Property name case mismatch "
                        f"(expected: '{expected_name}', found: '{actual_name}')"
                    )
                else:
                    issues.append(
                        f"❌ {database_name}: Missing required property '{expected_name}'"
                    )
        
        # Check for unexpected extra properties (informational only)
        extra_properties = set(actual_properties.keys()) - checked_properties
        if extra_properties:
            extra_list = ", ".join(sorted(extra_properties))
            issues.append(
                f"ℹ️  {database_name}: Additional properties found: {extra_list}"
            )
        
        # Determine if validation passed (no ❌ errors)
        has_errors = any(issue.startswith("❌") for issue in issues)
        
        if not issues:
            issues.append(f"✅ {database_name}: Schema validation passed")
            return True, issues
        elif not has_errors:
            # Only warnings/info, still valid
            issues.insert(0, f"✅ {database_name}: Schema validation passed with warnings")
            return True, issues
        else:
            issues.insert(0, f"❌ {database_name}: Schema validation FAILED")
            return False, issues
            
    except APIResponseError as e:
        issues.append(f"❌ {database_name}: API error - {e.message}")
        return False, issues
    except Exception as e:
        issues.append(f"❌ {database_name}: Validation error - {str(e)}")
        return False, issues


def validate_all_databases(
    notion_client: Client,
    database_ids: Dict[str, str]
) -> Dict[str, Tuple[bool, List[str]]]:
    """
    Validate all Notion databases.
    
    Args:
        notion_client: Authenticated Notion client
        database_ids: Dictionary mapping database names to their IDs:
            - task_board
            - trace_log
            - agent_health
            - knowledge_base
            - memory_archive
    
    Returns:
        Dictionary mapping database names to (is_valid, issues_list) tuples
    """
    results = {}
    
    # Map database keys to friendly names
    db_name_map = {
        "task_board": "Task Board",
        "trace_log": "Trace Log Index",
        "agent_health": "Agent Health Monitor",
        "knowledge_base": "Knowledge Base",
        "memory_archive": "Memory Archive"
    }
    
    for db_key, expected_schema in EXPECTED_SCHEMAS.items():
        db_id = database_ids.get(db_key)
        friendly_name = db_name_map.get(db_key, db_key)
        
        is_valid, issues = validate_database_schema(
            notion_client,
            db_id,
            friendly_name,
            expected_schema
        )
        
        results[db_key] = (is_valid, issues)
    
    return results


def print_validation_results(results: Dict[str, Tuple[bool, List[str]]]):
    """
    Print validation results to console in a user-friendly format.
    
    Args:
        results: Dictionary from validate_all_databases()
    """
    logger.info("=" * 70)
    logger.info("NOTION DATABASE SCHEMA VALIDATION")
    logger.info("=" * 70)
    
    all_valid = True
    
    for db_key, (is_valid, issues) in results.items():
        if not is_valid:
            all_valid = False
        
        for issue in issues:
            # Use appropriate log level based on issue type
            if issue.startswith("✅"):
                logger.info(issue)
            elif issue.startswith("⚠️"):
                logger.warning(issue)
            elif issue.startswith("ℹ️"):
                logger.info(issue)
            elif issue.startswith("❌"):
                logger.error(issue)
            else:
                logger.info(issue)
    
    logger.info("=" * 70)
    
    if all_valid:
        logger.info("✅ All database schemas validated successfully")
    else:
        logger.warning("⚠️  Some databases have schema issues - bot will continue but may encounter errors")
    
    logger.info("=" * 70)

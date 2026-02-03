"""
Tests for Notion schema validation functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
from notion_client.errors import APIResponseError
from notion_validator import (
    validate_database_schema,
    validate_all_databases,
    print_validation_results,
    EXPECTED_SCHEMAS
)


class TestNotionSchemaValidation:
    """Tests for Notion schema validation."""

    def test_expected_schemas_structure(self):
        """Test that expected schemas are properly defined."""
        assert "task_board" in EXPECTED_SCHEMAS
        assert "trace_log" in EXPECTED_SCHEMAS
        assert "agent_health" in EXPECTED_SCHEMAS
        assert "knowledge_base" in EXPECTED_SCHEMAS
        assert "memory_archive" in EXPECTED_SCHEMAS
        
        # Check task_board schema
        task_schema = EXPECTED_SCHEMAS["task_board"]
        assert task_schema["Task"] == "title"
        assert task_schema["Status"] == "select"
        assert task_schema["Priority"] == "select"

    def test_validate_database_schema_missing_id(self):
        """Test validation when database ID is not configured."""
        mock_client = MagicMock()
        
        is_valid, issues = validate_database_schema(
            mock_client,
            None,  # No database ID
            "Test Database",
            {"Property": "title"}
        )
        
        assert not is_valid
        assert len(issues) == 1
        assert "Database ID not configured" in issues[0]

    def test_validate_database_schema_perfect_match(self):
        """Test validation with perfect schema match."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.return_value = {
            "properties": {
                "Task": {"type": "title"},
                "Status": {"type": "select"}
            }
        }
        
        expected_schema = {
            "Task": "title",
            "Status": "select"
        }
        
        is_valid, issues = validate_database_schema(
            mock_client,
            "test_db_id",
            "Test Database",
            expected_schema
        )
        
        assert is_valid
        assert any("validation passed" in issue.lower() for issue in issues)

    def test_validate_database_schema_case_mismatch(self):
        """Test validation with case-insensitive property name match."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.return_value = {
            "properties": {
                "task": {"type": "title"},  # lowercase instead of 'Task'
                "Status": {"type": "select"}
            }
        }
        
        expected_schema = {
            "Task": "title",
            "Status": "select"
        }
        
        is_valid, issues = validate_database_schema(
            mock_client,
            "test_db_id",
            "Test Database",
            expected_schema
        )
        
        # Should pass with warning
        assert is_valid
        assert any("case mismatch" in issue.lower() for issue in issues)

    def test_validate_database_schema_missing_property(self):
        """Test validation with missing required property."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.return_value = {
            "properties": {
                "Task": {"type": "title"}
                # Missing 'Status' property
            }
        }
        
        expected_schema = {
            "Task": "title",
            "Status": "select"
        }
        
        is_valid, issues = validate_database_schema(
            mock_client,
            "test_db_id",
            "Test Database",
            expected_schema
        )
        
        assert not is_valid
        assert any("Missing required property" in issue for issue in issues)

    def test_validate_database_schema_wrong_type(self):
        """Test validation with wrong property type."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.return_value = {
            "properties": {
                "Task": {"type": "title"},
                "Status": {"type": "rich_text"}  # Wrong type, should be 'select'
            }
        }
        
        expected_schema = {
            "Task": "title",
            "Status": "select"
        }
        
        is_valid, issues = validate_database_schema(
            mock_client,
            "test_db_id",
            "Test Database",
            expected_schema
        )
        
        assert not is_valid
        assert any("wrong type" in issue.lower() for issue in issues)

    def test_validate_database_schema_api_error(self):
        """Test validation handles API errors gracefully."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.side_effect = APIResponseError(
            response=MagicMock(status_code=404),
            message="Database not found",
            code="object_not_found"
        )
        
        is_valid, issues = validate_database_schema(
            mock_client,
            "test_db_id",
            "Test Database",
            {"Property": "title"}
        )
        
        assert not is_valid
        assert any("API error" in issue for issue in issues)

    def test_validate_all_databases(self):
        """Test validation of all databases."""
        mock_client = MagicMock()
        mock_client.databases.retrieve.return_value = {
            "properties": {
                "Task": {"type": "title"},
                "Status": {"type": "select"},
                "Priority": {"type": "select"},
                "Assigned To": {"type": "select"},
                "Trigger Source": {"type": "select"},
                "Trace Link": {"type": "url"},
                "Blocker Reason": {"type": "rich_text"}
            }
        }
        
        database_ids = {
            "task_board": "test_task_id",
            "trace_log": "test_trace_id",
            "agent_health": "test_health_id",
            "knowledge_base": "test_kb_id",
            "memory_archive": "test_memory_id"
        }
        
        results = validate_all_databases(mock_client, database_ids)
        
        assert len(results) == 5
        assert "task_board" in results
        assert "trace_log" in results
        assert "agent_health" in results
        assert "knowledge_base" in results
        assert "memory_archive" in results

    def test_validate_all_databases_missing_id(self):
        """Test validation when some database IDs are missing."""
        mock_client = MagicMock()
        
        database_ids = {
            "task_board": "test_task_id",
            "trace_log": None,  # Missing
            "agent_health": None,  # Missing
            "knowledge_base": None,  # Missing
            "memory_archive": None  # Missing
        }
        
        results = validate_all_databases(mock_client, database_ids)
        
        # Should still validate all databases
        assert len(results) == 5
        
        # Check that missing IDs are reported
        for db_key in ["trace_log", "agent_health", "knowledge_base", "memory_archive"]:
            is_valid, issues = results[db_key]
            assert not is_valid
            assert any("not configured" in issue for issue in issues)

    def test_print_validation_results(self, caplog):
        """Test that validation results are printed correctly."""
        import logging
        caplog.set_level(logging.INFO)
        
        results = {
            "task_board": (True, ["✅ Task Board: Schema validation passed"]),
            "trace_log": (False, ["❌ Trace Log Index: Missing required property 'Trace ID'"]),
            "agent_health": (True, ["✅ Agent Health Monitor: Schema validation passed with warnings",
                                   "⚠️  Agent Health Monitor: Property name case mismatch"])
        }
        
        print_validation_results(results)
        
        # Check that log messages were created
        assert any("NOTION DATABASE SCHEMA VALIDATION" in record.message for record in caplog.records)
        assert any("Task Board" in record.message for record in caplog.records)
        assert any("Trace Log Index" in record.message for record in caplog.records)

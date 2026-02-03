"""
Unit tests for helper functions in calyx.py
"""

import pytest
import os
import uuid
from unittest.mock import patch, MagicMock
from calyx import (
    safe_get_notion_property,
    generate_trace_id,
    get_token_path,
    get_channel_context,
    init_channel_types,
)


class TestSafeGetNotionProperty:
    """Tests for safe_get_notion_property helper function."""
    
    def test_safe_get_notion_property_title(self, fake_notion_page):
        """Test extraction of title property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Name", "title")
        assert result == "Test Page"
    
    def test_safe_get_notion_property_title_missing(self):
        """Test title property with missing data."""
        props = {"Name": {"title": []}}
        result = safe_get_notion_property(props, "Name", "title", default="No Title")
        assert result == "No Title"
    
    def test_safe_get_notion_property_select(self, fake_notion_page):
        """Test extraction of select property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Status", "select")
        assert result == "Active"
    
    def test_safe_get_notion_property_select_missing(self):
        """Test select property with missing data."""
        props = {"Status": {"select": None}}
        result = safe_get_notion_property(props, "Status", "select", default="Unknown")
        assert result == "Unknown"
    
    def test_safe_get_notion_property_multi_select(self, fake_notion_page):
        """Test extraction of multi_select property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Tags", "multi_select")
        assert result == ["test", "important"]
    
    def test_safe_get_notion_property_multi_select_empty(self):
        """Test multi_select property with empty list."""
        props = {"Tags": {"multi_select": []}}
        result = safe_get_notion_property(props, "Tags", "multi_select")
        assert result == []
    
    def test_safe_get_notion_property_multi_select_with_nulls(self):
        """Test multi_select property filtering out null names."""
        props = {
            "Tags": {
                "multi_select": [
                    {"name": "valid"},
                    {"name": None},
                    {"name": ""},
                    {"name": "another"}
                ]
            }
        }
        result = safe_get_notion_property(props, "Tags", "multi_select")
        assert result == ["valid", "another"]
    
    def test_safe_get_notion_property_number(self, fake_notion_page):
        """Test extraction of number property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Count", "number")
        assert result == 42
    
    def test_safe_get_notion_property_number_missing(self):
        """Test number property with missing data."""
        props = {"Count": {"number": None}}
        result = safe_get_notion_property(props, "Count", "number", default=0)
        assert result == 0
    
    def test_safe_get_notion_property_checkbox(self, fake_notion_page):
        """Test extraction of checkbox property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Done", "checkbox")
        assert result is True
    
    def test_safe_get_notion_property_checkbox_default(self):
        """Test checkbox property with default False."""
        props = {"Done": {"checkbox": None}}
        result = safe_get_notion_property(props, "Done", "checkbox")
        assert result is False
    
    def test_safe_get_notion_property_date(self, fake_notion_page):
        """Test extraction of date property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "Date", "date")
        assert result == "2024-01-01T00:00:00.000Z"
    
    def test_safe_get_notion_property_date_missing(self):
        """Test date property with missing data."""
        props = {"Date": {"date": None}}
        result = safe_get_notion_property(props, "Date", "date", default="N/A")
        assert result == "N/A"
    
    def test_safe_get_notion_property_url(self, fake_notion_page):
        """Test extraction of url property."""
        props = fake_notion_page["properties"]
        result = safe_get_notion_property(props, "URL", "url")
        assert result == "https://example.com"
    
    def test_safe_get_notion_property_url_missing(self):
        """Test url property with missing data."""
        props = {"URL": {"url": None}}
        result = safe_get_notion_property(props, "URL", "url", default="")
        assert result == ""
    
    def test_safe_get_notion_property_missing_property(self):
        """Test with completely missing property."""
        props = {}
        result = safe_get_notion_property(props, "NonExistent", "title", default="Default")
        assert result == "Default"
    
    def test_safe_get_notion_property_unsupported_type(self):
        """Test with unsupported property type."""
        props = {"Custom": {"custom": "value"}}
        result = safe_get_notion_property(props, "Custom", "unsupported", default="Default")
        assert result == "Default"
    
    def test_safe_get_notion_property_exception_handling(self):
        """Test exception handling for malformed data."""
        props = {"Bad": "not_a_dict"}
        result = safe_get_notion_property(props, "Bad", "title", default="Safe")
        assert result == "Safe"


class TestGenerateTraceId:
    """Tests for generate_trace_id function."""
    
    def test_generate_trace_id_format(self):
        """Test trace ID has correct format."""
        trace_id = generate_trace_id()
        assert trace_id.startswith("TRC-")
        assert len(trace_id) == 12  # "TRC-" + 8 hex chars
    
    def test_generate_trace_id_uniqueness(self):
        """Test that generated trace IDs are unique."""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # All unique
    
    def test_generate_trace_id_uppercase(self):
        """Test that trace ID hex portion is uppercase."""
        trace_id = generate_trace_id()
        hex_part = trace_id[4:]  # Skip "TRC-"
        assert hex_part.isupper()


class TestGetTokenPath:
    """Tests for get_token_path function."""
    
    def test_get_token_path_gmail(self):
        """Test token path for gmail service."""
        path = get_token_path("gmail")
        assert path.endswith("gmail_token.json")
        assert "tokens" in path
    
    def test_get_token_path_calendar(self):
        """Test token path for calendar service."""
        path = get_token_path("calendar")
        assert path.endswith("calendar_token.json")
        assert "tokens" in path
    
    def test_get_token_path_case_insensitive(self):
        """Test that service name is lowercased."""
        path1 = get_token_path("GMAIL")
        path2 = get_token_path("gmail")
        assert path1 == path2


class TestChannelContext:
    """Tests for channel context functions."""
    
    def test_init_channel_types(self, mock_env_vars):
        """Test channel types initialization."""
        # Import inside test to get fresh environment
        import importlib
        import calyx
        importlib.reload(calyx)
        
        calyx.init_channel_types()
        assert len(calyx.CHANNEL_TYPES) == 5
        assert "123456789" in calyx.CHANNEL_TYPES
    
    def test_get_channel_context_known(self, mock_env_vars):
        """Test getting context for known channel."""
        # Import inside test to get fresh environment
        import importlib
        import calyx
        importlib.reload(calyx)
        
        calyx.init_channel_types()
        context = calyx.get_channel_context("123456789")
        assert context == "the-well"
    
    def test_get_channel_context_unknown(self, mock_env_vars):
        """Test getting context for unknown channel."""
        from calyx import get_channel_context
        context = get_channel_context("999999999")
        assert context == "unknown"

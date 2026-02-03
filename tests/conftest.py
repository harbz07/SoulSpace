"""
Pytest configuration and fixtures for SoulSpace Calyx tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    env_vars = {
        "DISCORD_TOKEN": "test_discord_token",
        "NOTION_TOKEN": "test_notion_token",
        "NOTION_TASK_BOARD_ID": "test_task_board_id",
        "NOTION_TRACE_LOG_ID": "test_trace_log_id",
        "NOTION_AGENT_HEALTH_ID": "test_agent_health_id",
        "NOTION_KNOWLEDGE_BASE_ID": "test_kb_id",
        "NOTION_MEMORY_ARCHIVE_ID": "test_memory_id",
        "JOURNAL_DB_ID": "test_journal_id",
        "CHANNEL_THE_WELL": "123456789",
        "CHANNEL_ENGINE_LOGS": "987654321",
        "CHANNEL_THE_SCREAM": "111222333",
        "CHANNEL_THE_MIRROR": "444555666",
        "CHANNEL_THE_COUNSEL": "777888999",
        "GOOGLE_CLIENT_ID": "test_client_id",
        "GOOGLE_CLIENT_SECRET": "test_client_secret",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_notion_client():
    """Mock Notion client with fake responses."""
    client = MagicMock()
    
    # Mock users.me() for authentication
    client.users.me.return_value = {"id": "test_user_id"}
    
    # Mock pages.create()
    client.pages.create.return_value = {
        "id": "test_page_id",
        "properties": {}
    }
    
    # Mock pages.update()
    client.pages.update.return_value = {
        "id": "test_page_id",
        "properties": {}
    }
    
    # Mock databases.query()
    client.databases.query.return_value = {
        "results": [],
        "has_more": False
    }
    
    return client


@pytest.fixture
def mock_discord_bot():
    """Mock Discord bot instance."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.name = "TestBot"
    bot.user.id = 123456
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False
    bot.latency = 0.05
    bot.guilds = []
    
    # Mock get_channel
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock(return_value=MagicMock(id=999))
    bot.get_channel.return_value = mock_channel
    
    return bot


@pytest.fixture
def mock_discord_message():
    """Mock Discord message object."""
    message = MagicMock()
    message.id = 123456789
    message.author = MagicMock()
    message.author.bot = False
    message.author.name = "TestUser"
    message.author.id = 987654321
    message.content = "Test message content"
    message.channel = MagicMock()
    message.channel.id = 123456789
    message.channel.name = "test-channel"
    message.jump_url = "https://discord.com/channels/123/456/789"
    message.created_at = MagicMock()
    return message


@pytest.fixture
def mock_discord_interaction():
    """Mock Discord interaction object."""
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = 987654321
    interaction.user.name = "TestUser"
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def fake_notion_page():
    """Fake Notion page response with properties."""
    return {
        "id": "test_page_id",
        "properties": {
            "Name": {
                "title": [{"text": {"content": "Test Page"}}]
            },
            "Status": {
                "select": {"name": "Active"}
            },
            "Priority": {
                "select": {"name": "High"}
            },
            "Tags": {
                "multi_select": [
                    {"name": "test"},
                    {"name": "important"}
                ]
            },
            "Count": {
                "number": 42
            },
            "Done": {
                "checkbox": True
            },
            "Date": {
                "date": {"start": "2024-01-01T00:00:00.000Z"}
            },
            "URL": {
                "url": "https://example.com"
            }
        }
    }


@pytest.fixture
def fake_notion_database_response():
    """Fake Notion database query response."""
    return {
        "results": [
            {
                "id": "page_1",
                "properties": {
                    "Agent Name": {
                        "title": [{"text": {"content": "TestAgent"}}]
                    },
                    "Status": {
                        "select": {"name": "Active"}
                    }
                }
            }
        ],
        "has_more": False,
        "next_cursor": None
    }


@pytest.fixture
def mock_google_oauth_flow():
    """Mock Google OAuth flow."""
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://oauth.example.com", "state123")
    
    mock_credentials = MagicMock()
    mock_credentials.token = "test_token"
    mock_credentials.refresh_token = "test_refresh_token"
    mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
    mock_credentials.client_id = "test_client_id"
    mock_credentials.client_secret = "test_client_secret"
    mock_credentials.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    
    flow.fetch_token.return_value = None
    flow.credentials = mock_credentials
    
    return flow

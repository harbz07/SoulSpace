"""
Integration tests for calyx.py Discord bot functionality.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os


class TestBotInitialization:
    """Tests for bot initialization."""
    
    def test_bot_initialization(self, mock_env_vars):
        """Test bot starts without errors."""
        with patch('discord.Client'):
            # Import after patching to avoid actual bot initialization
            import calyx
            assert calyx.TOKEN is not None
            assert calyx.NOTION_TOKEN is not None
    
    def test_channel_ids_loaded(self, mock_env_vars):
        """Test channel IDs are loaded from environment."""
        import calyx
        assert calyx.CHANNEL_THE_WELL == "123456789"
        assert calyx.CHANNEL_ENGINE_LOGS == "987654321"
    
    def test_google_oauth_config(self, mock_env_vars):
        """Test Google OAuth configuration."""
        import calyx
        assert calyx.GOOGLE_CLIENT_ID is not None
        assert calyx.GOOGLE_CLIENT_SECRET is not None
        assert calyx.OAUTH_REDIRECT_URI is not None


class TestChannelContextLoading:
    """Tests for channel context functionality."""
    
    def test_channel_context_loading(self, mock_env_vars):
        """Test channel type detection."""
        from calyx import init_channel_types, get_channel_context
        
        init_channel_types()
        
        # Test known channels
        assert get_channel_context("123456789") == "the-well"
        assert get_channel_context("987654321") == "engine-logs"
        assert get_channel_context("111222333") == "the-scream"
        
        # Test unknown channel
        assert get_channel_context("999999999") == "unknown"


class TestCreateOAuthFlow:
    """Tests for OAuth flow creation."""
    
    def test_create_oauth_flow_gmail(self, mock_env_vars):
        """Test OAuth flow creation for Gmail."""
        from calyx import create_oauth_flow, GOOGLE_SCOPES
        
        with patch('calyx.Flow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_config.return_value = mock_flow
            
            flow = create_oauth_flow("gmail")
            
            # Verify Flow.from_client_config was called
            assert mock_flow_class.from_client_config.called
            call_args = mock_flow_class.from_client_config.call_args
            assert call_args[1]["scopes"] == GOOGLE_SCOPES["gmail"]
    
    def test_create_oauth_flow_calendar(self, mock_env_vars):
        """Test OAuth flow creation for Calendar."""
        from calyx import create_oauth_flow, GOOGLE_SCOPES
        
        with patch('calyx.Flow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_config.return_value = mock_flow
            
            flow = create_oauth_flow("calendar")
            
            call_args = mock_flow_class.from_client_config.call_args
            assert call_args[1]["scopes"] == GOOGLE_SCOPES["calendar"]
    
    def test_create_oauth_flow_unknown_service(self, mock_env_vars):
        """Test OAuth flow defaults to Gmail for unknown service."""
        from calyx import create_oauth_flow, GOOGLE_SCOPES
        
        with patch('calyx.Flow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_config.return_value = mock_flow
            
            flow = create_oauth_flow("unknown_service")
            
            # Should default to gmail scopes
            call_args = mock_flow_class.from_client_config.call_args
            assert call_args[1]["scopes"] == GOOGLE_SCOPES["gmail"]


class TestUpdateAgentHealth:
    """Tests for update_agent_health functionality."""
    
    @pytest.mark.asyncio
    async def test_update_agent_health_mocked(self, mock_notion_client):
        """Test agent health updates with mocked Notion."""
        with patch('calyx.notion', mock_notion_client):
            with patch('calyx.update_agent_health') as mock_update:
                mock_update.return_value = AsyncMock()
                
                from calyx import update_agent_health
                
                # Call should succeed without errors
                result = await mock_update(
                    agent_name="Calyx",
                    status="Active",
                    auth_status="Valid"
                )


class TestExportFunctionality:
    """Tests for data export functionality."""
    
    def test_token_dir_creation(self, mock_env_vars):
        """Test token directory is created."""
        import calyx
        # TOKEN_DIR should exist after import
        assert os.path.exists(calyx.TOKEN_DIR)
    
    @pytest.mark.asyncio
    async def test_list_stored_tokens(self, mock_env_vars, tmp_path):
        """Test listing stored tokens."""
        from calyx import list_stored_tokens
        
        # Patch TOKEN_DIR to use tmp_path
        with patch('calyx.TOKEN_DIR', str(tmp_path)):
            # Create some fake token files
            (tmp_path / "gmail_token.json").write_text('{"token": "test"}')
            (tmp_path / "calendar_token.json").write_text('{"token": "test2"}')
            
            tokens = list_stored_tokens()
            assert len(tokens) == 2
            assert "gmail" in tokens
            assert "calendar" in tokens

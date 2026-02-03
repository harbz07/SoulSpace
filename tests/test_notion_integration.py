"""
Integration tests for Notion integration functions.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from calyx_notion_integration import log_trace, create_task, update_agent_health


class TestLogTrace:
    """Tests for log_trace function."""
    
    @pytest.mark.asyncio
    async def test_log_trace_success(self, mock_notion_client):
        """Test successful trace logging."""
        with patch('calyx_notion_integration.notion', mock_notion_client):
            await log_trace(
                trace_id="TRC-TEST123",
                request_summary="Test request",
                agent_chain="Agent1 → Agent2",
                data_sources=["Source1", "Source2"],
                discord_link="https://discord.com/test",
                success=True
            )
            
            # Verify notion.pages.create was called
            assert mock_notion_client.pages.create.called
            call_args = mock_notion_client.pages.create.call_args
            assert call_args[1]["properties"]["Trace ID"]["title"][0]["text"]["content"] == "TRC-TEST123"
    
    @pytest.mark.asyncio
    async def test_log_trace_failure(self, mock_notion_client):
        """Test trace logging handles failures gracefully."""
        mock_notion_client.pages.create.side_effect = Exception("API Error")
        
        with patch('calyx_notion_integration.notion', mock_notion_client):
            # Should not raise exception
            await log_trace(
                trace_id="TRC-TEST456",
                request_summary="Test request",
                agent_chain="Agent1",
                data_sources=["Source1"],
                discord_link="https://discord.com/test",
                success=False
            )


class TestCreateTask:
    """Tests for create_task function."""
    
    @pytest.mark.asyncio
    async def test_create_task_minimal(self, mock_notion_client):
        """Test task creation with minimal parameters."""
        with patch('calyx_notion_integration.notion', mock_notion_client):
            await create_task(task_name="Test Task")
            
            assert mock_notion_client.pages.create.called
            call_args = mock_notion_client.pages.create.call_args
            props = call_args[1]["properties"]
            assert props["Task"]["title"][0]["text"]["content"] == "Test Task"
            assert props["Status"]["select"]["name"] == "To-Do"
            assert props["Priority"]["select"]["name"] == "Medium"
    
    @pytest.mark.asyncio
    async def test_create_task_full_parameters(self, mock_notion_client):
        """Test task creation with all parameters."""
        with patch('calyx_notion_integration.notion', mock_notion_client):
            await create_task(
                task_name="Full Test Task",
                status="Executing",
                priority="Critical",
                assigned_to="Harvey",
                trigger_source="API",
                trace_link="https://discord.com/trace",
                blocker_reason="Waiting for approval"
            )
            
            assert mock_notion_client.pages.create.called
            call_args = mock_notion_client.pages.create.call_args
            props = call_args[1]["properties"]
            assert props["Task"]["title"][0]["text"]["content"] == "Full Test Task"
            assert props["Status"]["select"]["name"] == "Executing"
            assert props["Priority"]["select"]["name"] == "Critical"
            assert props["Assigned To"]["select"]["name"] == "Harvey"
            assert props["Trace Link"]["url"] == "https://discord.com/trace"
    
    @pytest.mark.asyncio
    async def test_create_task_error_handling(self, mock_notion_client):
        """Test task creation handles errors gracefully."""
        mock_notion_client.pages.create.side_effect = Exception("Database full")
        
        with patch('calyx_notion_integration.notion', mock_notion_client):
            # Should not raise exception
            await create_task(task_name="Error Task")


class TestUpdateAgentHealth:
    """Tests for update_agent_health function."""
    
    @pytest.mark.asyncio
    async def test_update_agent_health_existing(self, mock_notion_client, fake_notion_database_response):
        """Test updating health for existing agent."""
        mock_notion_client.databases.query.return_value = fake_notion_database_response
        
        with patch('calyx_notion_integration.notion', mock_notion_client):
            await update_agent_health(
                agent_name="TestAgent",
                status="Active",
                execution_count=100,
                error_count=5,
                last_error="Test error",
                auth_status="Valid"
            )
            
            # Should query first
            assert mock_notion_client.databases.query.called
            # Should update existing page
            assert mock_notion_client.pages.update.called
            call_args = mock_notion_client.pages.update.call_args
            props = call_args[1]["properties"]
            assert props["Agent Name"]["title"][0]["text"]["content"] == "TestAgent"
            assert props["Status"]["select"]["name"] == "Active"
    
    @pytest.mark.asyncio
    async def test_update_agent_health_new(self, mock_notion_client):
        """Test creating health entry for new agent."""
        # Return empty results (agent doesn't exist)
        mock_notion_client.databases.query.return_value = {"results": [], "has_more": False}
        
        with patch('calyx_notion_integration.notion', mock_notion_client):
            await update_agent_health(
                agent_name="NewAgent",
                status="Active",
                auth_status="Valid"
            )
            
            # Should query first
            assert mock_notion_client.databases.query.called
            # Should create new page
            assert mock_notion_client.pages.create.called
            call_args = mock_notion_client.pages.create.call_args
            props = call_args[1]["properties"]
            assert props["Agent Name"]["title"][0]["text"]["content"] == "NewAgent"
    
    @pytest.mark.asyncio
    async def test_update_agent_health_error_handling(self, mock_notion_client):
        """Test agent health update handles errors gracefully."""
        mock_notion_client.databases.query.side_effect = Exception("Connection timeout")
        
        with patch('calyx_notion_integration.notion', mock_notion_client):
            # Should not raise exception
            await update_agent_health(
                agent_name="ErrorAgent",
                status="Error"
            )

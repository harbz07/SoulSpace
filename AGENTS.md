# SoulSpace Calyx - Agent Guide

This document provides essential information for AI coding agents working on the SoulSpace Calyx project.

## Project Overview

**SoulSpace Calyx** is a single-user Discord bot orchestration system that uses:
- **Discord** as the nervous system (real-time communication and commands)
- **Notion** as persistent memory (5 specialized databases)
- **Calyx** as the orchestrator (coordinates agents, executes code, manages state)

The project is part of the **Vessel Framework** — a personal AI assistant orchestration layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SoulSpace Platform                          │
│                                                                     │
│  ┌─────────────┐    slash commands    ┌───────────────────────────┐ │
│  │   Calyx     │ ◄──────────────────► │       Discord             │ │
│  │  (Python)   │                      │   (Nervous System)        │ │
│  │             │  events/responses    │                           │ │
│  │ orchestrator│ ────────────────────►│  #the-well   (chat)       │ │
│  │             │                      │  #engine-logs (traces)    │ │
│  └──────┬──────┘                      │  #the-scream  (errors)    │ │
│         │                             │  #the-mirror  (status)    │ │
│         │ Notion API                  │  #the-counsel (control)   │ │
│         ▼                             └───────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Notion (Persistent Memory)                │    │
│  │                                                             │    │
│  │  Task Board │ Trace Log │ Agent Health │ Knowledge │ Memory │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │          MindBridge (LLM Router — TypeScript/Node.js)        │   │
│  │                                                              │   │
│  │  stdio (MCP)  │  HTTP/SSE  │  Cloudflare Worker             │   │
│  │  OpenAI · Anthropic · Google · DeepSeek · Ollama · More     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Orchestrator | Python 3.10+, discord.py 2.4.0, aiohttp |
| Notion Integration | notion-client 2.2.1 |
| Google OAuth | google-auth-oauthlib 1.2.0 |
| LLM Router | TypeScript, Node.js 18+, @modelcontextprotocol/sdk |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Health Server | aiohttp (port 8080) |

## Project Structure

```
/
├── calyx.py                      # Main Discord bot (1,361 lines)
├── calyx_notion_integration.py   # Notion API helpers
├── notion_validator.py           # Database schema validation
├── health_server.py              # HTTP health check endpoints
├── requirements.txt              # Python dependencies
├── pytest.ini                   # Test configuration
├── smoke_test.sh                # Quick validation script
├── .env.example                 # Environment template
│
├── mindbridge/                  # LLM Router (TypeScript)
│   ├── package.json
│   ├── src/                     # Source code
│   ├── dist/                    # Compiled output
│   ├── worker/                  # Cloudflare Worker
│   └── README.md
│
├── tests/                       # Python test suite
│   ├── conftest.py              # Pytest fixtures
│   ├── test_calyx.py
│   ├── test_notion_integration.py
│   ├── test_notion_validator.py
│   └── test_helpers.py
│
├── wiki/                        # Documentation
├── logs/                        # Runtime logs (gitignored)
├── tokens/                      # OAuth tokens (gitignored)
└── venv/                        # Python virtual env
```

## Key Files

| File | Purpose |
|------|---------|
| `calyx.py` | Main bot with Discord commands, OAuth flows, code execution |
| `calyx_notion_integration.py` | Async helpers: `log_trace()`, `create_task()`, `update_agent_health()` |
| `notion_validator.py` | Validates 5 Notion database schemas on startup |
| `health_server.py` | Aiohttp server with `/health`, `/health/live`, `/health/ready`, `/metrics` |
| `mindbridge/` | Complete TypeScript MCP server for LLM routing |

## Environment Variables

Copy `.env.example` to `.env` and configure:

**Discord:**
- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `CHANNEL_THE_WELL` - Main interaction channel ID
- `CHANNEL_ENGINE_LOGS` - System trace logs channel ID
- `CHANNEL_THE_SCREAM` - Error notifications channel ID
- `CHANNEL_THE_MIRROR` - Status updates channel ID
- `CHANNEL_THE_COUNSEL` - Commands/control channel ID

**Notion:**
- `NOTION_TOKEN` - Integration token
- `NOTION_TASK_BOARD_ID`
- `NOTION_TRACE_LOG_ID`
- `NOTION_AGENT_HEALTH_ID`
- `NOTION_KNOWLEDGE_BASE_ID`
- `NOTION_MEMORY_ARCHIVE_ID`

**Google OAuth (optional):**
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

**Operational:**
- `OAUTH_REDIRECT_PORT=9090`
- `START_PAUSED=false`

## Build and Run Commands

### Python Bot (Calyx)

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials

# Run
python calyx.py

# Development
python calyx.py  # Auto-reload not built-in, restart on changes
```

### Testing

```bash
# Run all tests
pytest tests/

# Run with coverage (configured in pytest.ini)
pytest tests/ --cov --cov-report=html

# Quick smoke test
./smoke_test.sh

# Run specific test file
pytest tests/test_helpers.py -v

# Run with markers
pytest tests/ -m "not slow"
```

### MindBridge (TypeScript)

```bash
cd mindbridge
npm install

# Build
npm run build

# Run MCP server (stdio for Claude Desktop/Cursor)
npm start

# Run HTTP server (for web AI integrations)
npm run start:remote

# Cloudflare Worker
npm run worker:dev     # Local development
npm run worker:deploy  # Deploy to production

# Lint and format
npm run lint
npm run format
```

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/auth <service>` | Authenticate Gmail, Calendar, or Notion |
| `/status` | Show all agent health + last execution times |
| `/pause` | Suspend all automated triggers |
| `/resume` | Re-enable automated operations |
| `/trace <trace_id>` | Get raw logs for specific trace ID |
| `/soul <parameter> <value>` | Adjust alignment parameters |
| `/export` | Generate full data dump for backup |
| `/purge <memory_id>` | Delete specific memory (with confirmation) |
| `/exec <code>` | Execute Python code (30s timeout) |
| `/shell <command>` | Execute shell command (30s timeout, safety checks) |

## Testing Strategy

### Test Organization

- **`tests/conftest.py`** - Shared fixtures (mock Discord bot, Notion client, OAuth flow)
- **`tests/test_helpers.py`** - Unit tests for utility functions
- **`tests/test_calyx.py`** - Bot initialization and OAuth flow tests
- **`tests/test_notion_integration.py`** - Notion API integration tests
- **`tests/test_notion_validator.py`** - Schema validation tests

### Key Fixtures

```python
# From conftest.py
mock_env_vars           # Mock environment variables
mock_notion_client      # Mock Notion client with fake responses
mock_discord_bot        # Mock Discord bot instance
mock_discord_message    # Mock message object
fake_notion_page        # Fake Notion page with properties
mock_google_oauth_flow  # Mock OAuth flow
```

### Writing Tests

```python
# Example test pattern
def test_feature_name():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_output

# Async test
@pytest.mark.asyncio
async def test_async_feature():
    result = await my_async_function()
    assert result is not None
```

## Code Style Guidelines

### Python

- Follow PEP 8
- Use type hints where practical
- Document functions with docstrings
- Use `logger` from logging module (not print)
- Handle exceptions gracefully with try/except blocks
- Use `safe_get_notion_property()` for accessing Notion properties

### TypeScript (MindBridge)

- ESLint + Prettier configuration included
- Run `npm run lint` before committing
- Run `npm run format` to auto-format

## Security Considerations

⚠️ **This is a single-user system by design.**

The `/exec` and `/shell` commands allow arbitrary code execution:

- Shell command blacklist blocks dangerous commands (`rm -rf`, `dd`, etc.)
- 30-second timeout prevents runaway processes
- All executions logged with trace IDs
- Failures posted to `#the-scream` channel

**Recommendations:**
- Run in sandboxed environment
- Use low-privilege user account
- Don't expose to untrusted users
- Monitor execution logs regularly

## Notion Database Schemas

The 5 required databases must have specific properties. See `notion_validator.py` for the `EXPECTED_SCHEMAS` definition.

**Task Board:**
- `Task` (title), `Status` (select), `Priority` (select)
- `Assigned To` (select), `Trigger Source` (select)
- `Trace Link` (url), `Blocker Reason` (rich_text)

**Trace Log Index:**
- `Trace ID` (title), `Timestamp` (date), `Request Summary` (rich_text)
- `Agent Chain` (rich_text), `Data Sources Used` (multi_select)
- `Discord Link` (url), `Success` (checkbox)

**Agent Health Monitor:**
- `Agent Name` (title), `Status` (select), `Last Execution` (date)
- `Execution Count` (number), `Error Count` (number)
- `Last Error Message` (rich_text), `Auth Status` (select)

**Knowledge Base:**
- `Entry Title` (title), `Category` (select), `Consent Level` (select)
- `Source` (select), `Last Verified` (date)

**Memory Archive:**
- `Memory ID` (title), `Type` (select), `Consent Status` (select)
- `Created Date` (date), `Last Accessed` (date), `Access Count` (number)
- `Retention Policy` (select), `Content Preview` (rich_text)

## Health Check Endpoints

Available at `http://localhost:8080`:

- `GET /health` - Basic status and uptime
- `GET /health/live` - Liveness probe (Kubernetes-style)
- `GET /health/ready` - Readiness probe (Discord + Notion connectivity)
- `GET /metrics` - Basic metrics (uptime, latency, guild count)

## Logging

Logs are written to `logs/` with rotation (10MB, 5 backups):

- `logs/calyx.log` - All log levels (DEBUG+)
- `logs/errors.log` - Errors only (ERROR+)

Log format includes timestamp, name, level, function, line number, and message.

## Trace System

Every operation gets a unique **Trace ID** (`TRC-XXXXXXXX`):

1. Generated at start of command handler
2. Logged to Discord `#engine-logs`
3. Written to Notion Trace Log Index
4. Included in command responses
5. Available for lookup via `/trace <id>`

## Common Tasks

### Adding a New Slash Command

1. Add `@bot.tree.command()` decorator in `calyx.py`
2. Use `@app_commands.describe()` for parameter descriptions
3. Use `@app_commands.choices()` for enum values
4. Generate trace ID at start: `trace_id = generate_trace_id()`
5. Log to engine: `await log_to_engine(bot, trace_id, ...)`
6. Create trace log: `await create_trace_log(trace_id, ...)`
7. Update agent health: `await update_agent_health(...)`

### Adding a New Notion Database Operation

1. Add function to `calyx_notion_integration.py`
2. Use `notion.pages.create()` or `notion.databases.query()`
3. Handle `APIResponseError` exceptions
4. Log success/failure with `logger.info()` / `logger.error()`

### Running Tests After Changes

```bash
# Quick validation
./smoke_test.sh

# Full test suite with coverage
pytest tests/ --cov --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Documentation

- `README.md` - Main project documentation
- `TESTING.md` - Detailed testing guide
- `wiki/` - Extended documentation (Architecture, Commands, Security, etc.)
- `mindbridge/README.md` - MindBridge-specific documentation
- `mindbridge/AGENT_MESH.md` - Agent migration architecture

## External Dependencies

- **Discord:** Requires bot token and privileged message content intent
- **Notion:** Requires integration token and database sharing
- **Google OAuth:** Optional, for Gmail/Calendar features
- **MindBridge:** Optional, for LLM routing capabilities

## Git Workflow

- `.gitignore` excludes: `.env`, `venv/`, `__pycache__/`, `logs/`, `tokens/`, `mindbridge/node_modules/`, `mindbridge/dist/`
- Do not commit credentials or tokens
- Do not commit `logs/` or `tokens/` directories

# SoulSpace Calyx - Vessel Framework

A single-user Discord bot orchestration system that uses Discord as a nervous system and Notion as persistent memory. Calyx serves as the central coordinating agent for the Vessel Framework, providing execution capabilities, memory management, and comprehensive observability.

## 🎯 Overview

The Vessel Framework is designed as a personal AI assistant orchestration layer:
- **Discord** acts as the nervous system (real-time communication and commands)
- **Notion** acts as persistent memory (databases for tasks, traces, health, knowledge, and memories)
- **Calyx** acts as the orchestrator (coordinates agents, executes code, manages state)

## ✨ Features

- 🤖 **Discord Bot**: Slash commands for interaction and control
- 📝 **Notion Integration**: Automatic logging to 5 specialized databases
- 🔐 **Google OAuth**: Gmail and Calendar authentication
- 🔍 **Schema Validation**: Startup checks for Notion database configuration
- ⚡ **Code Execution**: Run Python code and shell commands via Discord
- 📊 **Health Monitoring**: Built-in health check endpoints
- 📝 **Structured Logging**: File-rotated logs with multiple verbosity levels
- 🎯 **Trace System**: Every operation gets a unique trace ID for debugging

## 📋 Prerequisites

- **Python 3.10+** (tested with 3.12)
- **Discord Account** with a server where you have admin access
- **Notion Account** (free tier works)
- **Google Cloud Account** (optional, for Gmail/Calendar features)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/harbz07/SoulSpace.git
cd SoulSpace
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure all required values (see Configuration section below).

## ⚙️ Configuration

### Discord Setup

1. **Create a Discord Bot**
   - Go to https://discord.com/developers/applications
   - Click "New Application" and give it a name
   - Go to the "Bot" section
   - Click "Reset Token" and copy the token to `DISCORD_TOKEN` in `.env`
   - Enable "Message Content Intent" under "Privileged Gateway Intents"

2. **Invite Bot to Your Server**
   - Go to "OAuth2" > "URL Generator"
   - Select scopes: `bot`, `applications.commands`
   - Select bot permissions: `Send Messages`, `Manage Messages`, `Read Message History`, `Use Slash Commands`
   - Copy the generated URL and open it in browser to invite bot

3. **Get Channel IDs**
   - Enable Developer Mode: User Settings > Advanced > Developer Mode
   - Right-click on each channel and select "Copy ID"
   - Paste the IDs into `.env`:
     - `CHANNEL_THE_WELL` - Main interaction channel
     - `CHANNEL_ENGINE_LOGS` - System trace logs
     - `CHANNEL_THE_SCREAM` - Error notifications
     - `CHANNEL_THE_MIRROR` - Status updates
     - `CHANNEL_THE_COUNSEL` - Commands/control

### Notion Setup

1. **Create a Notion Integration**
   - Go to https://www.notion.so/my-integrations
   - Click "New integration"
   - Give it a name (e.g., "Calyx Bot")
   - Copy the "Internal Integration Token" to `NOTION_TOKEN` in `.env`

2. **Create the 5 Required Databases**

   You need to create 5 databases with specific schemas. For each database:

   **Task Board** (`NOTION_TASK_BOARD_ID`)
   - `Task` - Title property
   - `Status` - Select property (options: To-Do, Executing, Blocked, Done, Cancelled)
   - `Priority` - Select property (options: Critical, High, Medium, Low)
   - `Assigned To` - Select property (options: tinyNature, Calyx, Harvey, Claude, Other)
   - `Trigger Source` - Select property (options: Manual, TIME, EVENT, API)
   - `Trace Link` - URL property
   - `Blocker Reason` - Text property

   **Trace Log Index** (`NOTION_TRACE_LOG_ID`)
   - `Trace ID` - Title property
   - `Timestamp` - Date property
   - `Request Summary` - Text property
   - `Agent Chain` - Text property
   - `Data Sources Used` - Multi-select property
   - `Discord Link` - URL property
   - `Success` - Checkbox property

   **Agent Health Monitor** (`NOTION_AGENT_HEALTH_ID`)
   - `Agent Name` - Title property
   - `Status` - Select property (options: Active, Paused, Error, Disabled)
   - `Last Execution` - Date property
   - `Execution Count` - Number property
   - `Error Count` - Number property
   - `Last Error Message` - Text property
   - `Auth Status` - Select property (options: Valid, Expired, Invalid, N/A)

   **Knowledge Base** (`NOTION_KNOWLEDGE_BASE_ID`)
   - `Entry Title` - Title property
   - `Category` - Select property
   - `Consent Level` - Select property
   - `Source` - Select property
   - `Last Verified` - Date property

   **Memory Archive** (`NOTION_MEMORY_ARCHIVE_ID`)
   - `Memory ID` - Title property
   - `Type` - Select property
   - `Consent Status` - Select property
   - `Created Date` - Date property
   - `Last Accessed` - Date property
   - `Access Count` - Number property
   - `Retention Policy` - Select property
   - `Content Preview` - Text property

3. **Share Databases with Integration**
   - Open each database in Notion
   - Click "Share" in the top right
   - Invite your integration (it will appear in the dropdown)
   - Repeat for all 5 databases

4. **Get Database IDs**
   - Open each database in Notion (full-page view, not inline)
   - Copy the URL from your browser
   - The URL looks like: `https://notion.so/workspace/DATABASE_ID?v=VIEW_ID`
   - Extract the 32-character hex string (DATABASE_ID) between the last `/` and the `?`
   - Paste each ID into the corresponding variable in `.env`

### Google OAuth Setup (Optional)

Only needed if you want Gmail/Calendar integration:

1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Enable "Gmail API" and "Google Calendar API"
4. Go to "Credentials" > "Create Credentials" > "OAuth 2.0 Client ID"
5. Application type: "Desktop app"
6. Copy the Client ID and Client Secret to `.env`

## 🏃 Running the Bot

### Development Mode

```bash
python calyx.py
```

The bot will:
1. Validate all Notion database schemas on startup
2. Display validation results with ✅/❌/⚠️ indicators
3. Connect to Discord
4. Start the health check server on port 8080
5. Post a status message to #the-mirror

For detailed testing, commands reference, troubleshooting and more, see the full documentation in the repository.

## 📚 Commands Reference

### System Control
- **`/pause`** - Suspend all automated triggers
- **`/resume`** - Re-enable automated operations

### Information & Debugging
- **`/status`** - Show all agent health
- **`/trace <trace_id>`** - Get raw logs for specific trace ID

### Code Execution (⚠️ Single-user system!)
- **`/exec <code>`** - Execute Python code (30s timeout)
- **`/shell <command>`** - Execute shell command (30s timeout, safety checks)

### Authentication
- **`/auth <service>`** - Authenticate service (gmail, calendar)

### Data Management
- **`/export`** - Generate full data dump for backup
- **`/purge <memory_id>`** - Delete specific memory

## 🔒 Security Notes

⚠️ **This is a single-user system by design**. The `/exec` and `/shell` commands allow arbitrary code execution.

**Security measures**:
- Shell command blacklist blocks dangerous commands
- 30-second timeout prevents runaway processes
- All executions logged with trace IDs
- Failures posted to #the-scream channel

**Recommendations**:
- Run in sandboxed environment
- Use low-privilege user account
- Don't expose to untrusted users
- Monitor execution logs regularly

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov --cov-report=html

# Quick smoke test
./smoke_test.sh
```

## 🔧 Troubleshooting

See detailed troubleshooting guide in repository documentation covering:
- Schema validation failures
- OAuth callback timeouts
- Agent health not updating
- Bot won't start
- Commands not appearing

## 📝 Logging

Logs are automatically rotated (10MB, 5 backups):
- `logs/calyx.log` - Main log
- `logs/errors.log` - Errors only

## 🔗 Links

- **Discord Server**: https://discord.gg/QU7urpGV
- **Repository**: https://github.com/harbz07/SoulSpace

## 📊 Health Check Endpoints

Access at `http://localhost:8080/health`:
- `/health` - Basic status
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe
- `/metrics` - Basic metrics

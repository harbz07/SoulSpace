# Installation and Configuration

This guide walks through every step needed to get SoulSpace running from scratch.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Tested with 3.12 |
| Node.js | 18+ | Only needed for MindBridge |
| Discord account | — | Must have a server where you have admin access |
| Notion account | Free tier | — |
| Google Cloud account | — | Optional — only for Gmail / Calendar features |

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/harbz07/SoulSpace.git
cd SoulSpace
```

---

## Step 2 — Python Environment

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

---

## Step 3 — Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in each section as described below.

---

## Discord Setup

### 3a — Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** and give it a name.
3. Navigate to the **Bot** section.
4. Click **Reset Token** and copy the token → set `DISCORD_TOKEN` in `.env`.
5. Under **Privileged Gateway Intents**, enable **Message Content Intent**.

### 3b — Invite the Bot to Your Server

1. Go to **OAuth2 → URL Generator**.
2. Select scopes: `bot`, `applications.commands`.
3. Select bot permissions: `Send Messages`, `Manage Messages`, `Read Message History`, `Use Slash Commands`.
4. Copy the generated URL and open it in a browser to invite the bot.

### 3c — Get Channel IDs

1. Enable Developer Mode: **User Settings → Advanced → Developer Mode**.
2. Right-click each channel → **Copy ID**.
3. Set these variables in `.env`:

| Variable | Channel |
|----------|---------|
| `CHANNEL_THE_WELL` | Main interaction channel |
| `CHANNEL_ENGINE_LOGS` | System trace logs |
| `CHANNEL_THE_SCREAM` | Error notifications |
| `CHANNEL_THE_MIRROR` | Status updates |
| `CHANNEL_THE_COUNSEL` | Commands / control |

---

## Notion Setup

### 4a — Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **New integration** and give it a name (e.g. "Calyx Bot").
3. Copy the **Internal Integration Token** → set `NOTION_TOKEN` in `.env`.

### 4b — Create the Five Databases

You need to create five Notion databases with specific property schemas. For full schema details see [Notion Databases](Notion-Databases.md).

**Quick reference:**

| Database | Variable |
|----------|----------|
| Task Board | `NOTION_TASK_BOARD_ID` |
| Trace Log Index | `NOTION_TRACE_LOG_ID` |
| Agent Health Monitor | `NOTION_AGENT_HEALTH_ID` |
| Knowledge Base | `NOTION_KNOWLEDGE_BASE_ID` |
| Memory Archive | `NOTION_MEMORY_ARCHIVE_ID` |

There is also an optional **Glass Journal** broadcast database: `JOURNAL_DB_ID`.

### 4c — Share Databases with the Integration

For each database:

1. Open it in Notion (full-page view).
2. Click **Share** in the top right.
3. Invite your integration from the dropdown.

### 4d — Get Database IDs

1. Open each database in Notion (full-page view).
2. Copy the URL — it looks like:
   ```
   https://notion.so/workspace/<DATABASE_ID>?v=<VIEW_ID>
   ```
3. Extract the 32-character hex `DATABASE_ID` and paste it into `.env`.

---

## Google OAuth Setup (Optional)

Only required for Gmail / Calendar features.

1. Go to https://console.cloud.google.com/
2. Create or select a project.
3. Enable **Gmail API** and **Google Calendar API**.
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**.
5. Application type: **Desktop app**.
6. Copy Client ID → `GOOGLE_CLIENT_ID` and Client Secret → `GOOGLE_CLIENT_SECRET` in `.env`.

---

## Operational Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OAUTH_REDIRECT_PORT` | `9090` | Local port for OAuth callback handling |
| `START_PAUSED` | `false` | Start bot with automated triggers disabled |

---

## MindBridge Setup (Optional)

MindBridge is required only if you want multi-LLM routing.

```bash
cd mindbridge
npm install
npm run build
```

See [MindBridge](MindBridge.md) for configuration and deployment options.

---

## Running the Bot

```bash
# Make sure your virtual environment is active
python calyx.py
```

On startup, Calyx will:

1. Validate all five Notion database schemas.
2. Print validation results (`✅` / `⚠️` / `❌`).
3. Connect to Discord.
4. Start the health server on port 8080.
5. Post a status message to `#the-mirror`.

---

## Verifying the Installation

```bash
# Check the health endpoint
curl http://localhost:8080/health

# Run the test suite
pytest tests/

# Quick smoke test
./smoke_test.sh
```

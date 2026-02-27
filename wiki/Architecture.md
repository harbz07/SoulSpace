# Architecture

This page describes how the SoulSpace components fit together.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SoulSpace Platform                          │
│                                                                     │
│  ┌─────────────┐    slash commands    ┌───────────────────────────┐ │
│  │             │ ◄──────────────────► │       Discord             │ │
│  │   Calyx     │                      │   (Nervous System)        │ │
│  │  (Python)   │  events/responses    │                           │ │
│  │             │ ────────────────────►│  #the-well   (chat)       │ │
│  │ orchestrator│                      │  #engine-logs (traces)    │ │
│  │             │                      │  #the-scream  (errors)    │ │
│  └──────┬──────┘                      │  #the-mirror  (status)    │ │
│         │                             │  #the-counsel (control)   │ │
│         │ Notion API                  └───────────────────────────┘ │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Notion (Persistent Memory)                │    │
│  │                                                             │    │
│  │  Task Board │ Trace Log │ Agent Health │ Knowledge │ Memory │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │          MindBridge (LLM Router — TypeScript)                │   │
│  │                                                              │   │
│  │  stdio (MCP)  │  HTTP/SSE  │  Cloudflare Worker             │   │
│  │  OpenAI · Anthropic · Google · DeepSeek · Ollama · More     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Calyx — the Orchestrator

`calyx.py` is the heart of SoulSpace. It is a **Discord bot** built on `discord.py` that:

1. Connects to Discord and registers slash commands.
2. On startup, validates all five Notion database schemas via `notion_validator.py`.
3. Starts an HTTP health-check server (port 8080) via `health_server.py`.
4. Posts a startup status message to `#the-mirror`.
5. Listens for slash commands and routes them to the appropriate handler.
6. Logs every operation to Notion through `calyx_notion_integration.py`.

### Key modules

| File | Responsibility |
|------|----------------|
| `calyx.py` | Bot setup, slash command handlers, OAuth flow, code execution |
| `calyx_notion_integration.py` | Async helpers: `log_trace`, `create_task`, `update_agent_health` |
| `notion_validator.py` | Validates the property names and types of all five Notion databases |
| `health_server.py` | Aiohttp server exposing `/health`, `/health/live`, `/health/ready`, `/metrics` |

---

## Discord Channels

| Environment Variable | Channel Name | Purpose |
|---------------------|-------------|---------|
| `CHANNEL_THE_WELL` | `#the-well` | Primary interaction — user messages to Calyx |
| `CHANNEL_ENGINE_LOGS` | `#engine-logs` | Trace and execution logs |
| `CHANNEL_THE_SCREAM` | `#the-scream` | Error and failure alerts |
| `CHANNEL_THE_MIRROR` | `#the-mirror` | Status updates and startup messages |
| `CHANNEL_THE_COUNSEL` | `#the-counsel` | Control commands |

---

## Notion Databases

All five databases are written to by `calyx_notion_integration.py`. See [Notion Databases](Notion-Databases.md) for full property schemas.

| Database | Environment Variable | Purpose |
|----------|---------------------|---------|
| Task Board | `NOTION_TASK_BOARD_ID` | Track tasks, statuses, priorities |
| Trace Log Index | `NOTION_TRACE_LOG_ID` | Record execution traces for debugging |
| Agent Health Monitor | `NOTION_AGENT_HEALTH_ID` | Track agent status and error counts |
| Knowledge Base | `NOTION_KNOWLEDGE_BASE_ID` | Store verified information entries |
| Memory Archive | `NOTION_MEMORY_ARCHIVE_ID` | Long-term memory with retention policies |

---

## Trace System

Every operation carried out by Calyx is tagged with a **Trace ID** (a UUID prefixed with `TRACE-`). Traces are:

- Logged to the `#engine-logs` Discord channel.
- Written to the Notion Trace Log Index.
- Available for lookup via the `/trace` slash command.

---

## MindBridge

MindBridge is a **TypeScript/Node.js** sub-project located in `mindbridge/`. It acts as an LLM router and can run in three modes:

| Mode | Transport | Clients |
|------|-----------|---------|
| MCP stdio | stdin/stdout | Claude Desktop, Cursor, Windsurf |
| HTTP/SSE | `localhost:3000` | Claude.ai, ChatGPT Actions, Gemini Extensions |
| Cloudflare Worker | HTTPS | Any web client |

See [MindBridge](MindBridge.md) for full details.

---

## Data Flow — Typical Interaction

```
User types slash command in Discord
         │
         ▼
Calyx receives interaction
         │
         ├─► Generate Trace ID
         │
         ├─► Execute handler logic (code exec, OAuth, status query …)
         │
         ├─► Write trace to Notion Trace Log
         │
         ├─► Update Agent Health in Notion
         │
         └─► Respond to Discord + log to #engine-logs
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Orchestrator | Python 3.10+, discord.py, aiohttp |
| Persistent Memory | Notion API (notion-client) |
| Auth | Google OAuth 2.0 (google-auth-oauthlib) |
| LLM Router | TypeScript, Node.js, @modelcontextprotocol/sdk |
| Serverless | Cloudflare Workers (wrangler) |
| Testing | pytest, pytest-asyncio, unittest.mock |

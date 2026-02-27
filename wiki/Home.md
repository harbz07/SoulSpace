# SoulSpace Wiki

Welcome to the **SoulSpace** wiki — the central reference for the Calyx / Vessel Framework project.

---

## What is SoulSpace?

SoulSpace is a **single-user AI assistant orchestration platform** built around three core pillars:

| Pillar | Technology | Role |
|--------|-----------|------|
| **Nervous System** | Discord | Real-time commands, notifications, and interaction |
| **Persistent Memory** | Notion | Five specialized databases for tasks, traces, health, knowledge, and memories |
| **Orchestrator** | Calyx (Python) | Coordinates agents, executes code, and manages state |

The **MindBridge** sub-component acts as an LLM router, letting Claude.ai, ChatGPT, Gemini, and other AI tools call any configured model for second opinions and multi-model workflows.

---

## Project Map

```
SoulSpace/
├── calyx.py                      # Main Discord bot & orchestrator
├── calyx_notion_integration.py   # Notion write helpers (log_trace, create_task, update_agent_health)
├── health_server.py              # Aiohttp health-check server (port 8080)
├── notion_validator.py           # Startup schema validation for all 5 Notion databases
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── tests/                        # Pytest test suite
│   ├── conftest.py
│   ├── test_calyx.py
│   ├── test_helpers.py
│   ├── test_notion_integration.py
│   └── test_notion_validator.py
└── mindbridge/                   # LLM router (TypeScript / Node.js)
    ├── src/
    │   ├── server.ts             # MCP stdio server
    │   ├── remote-server.ts      # HTTP / Cloudflare Worker entrypoint
    │   ├── cli.ts
    │   ├── config.ts
    │   └── types.ts
    ├── worker/                   # Cloudflare Worker wrapper
    ├── wrangler.jsonc            # Cloudflare deployment config
    └── package.json
```

---

## Quick Start

```bash
# 1 — Clone
git clone https://github.com/harbz07/SoulSpace.git
cd SoulSpace

# 2 — Python environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3 — Configuration
cp .env.example .env
# Edit .env with your Discord token, Notion token, and database IDs

# 4 — Run the bot
python calyx.py
```

For the full setup walkthrough see [Installation and Configuration](Installation-and-Configuration.md).

---

## Wiki Pages

| Page | Description |
|------|-------------|
| [Architecture](Architecture.md) | System design, data flow, and component interactions |
| [Installation and Configuration](Installation-and-Configuration.md) | Step-by-step setup for Discord, Notion, Google OAuth |
| [Discord Bot Commands](Discord-Bot-Commands.md) | All slash commands and their usage |
| [Notion Databases](Notion-Databases.md) | Schemas for all five Notion databases |
| [MindBridge](MindBridge.md) | LLM router — providers, tools, deployment modes |
| [Agent Mesh](Agent-Mesh.md) | Experimental vessel migration architecture |
| [Health and Monitoring](Health-and-Monitoring.md) | Health endpoints, logging, and metrics |
| [Testing](Testing.md) | Running and writing tests |
| [Troubleshooting](Troubleshooting.md) | Common issues and fixes |
| [Security](Security.md) | Security model and best-practice recommendations |

---

## Community

- **Discord Server**: https://discord.gg/QU7urpGV
- **Repository**: https://github.com/harbz07/SoulSpace

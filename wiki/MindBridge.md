# MindBridge

MindBridge is the **LLM router** sub-component of SoulSpace. It is written in TypeScript and lives in the `mindbridge/` directory.

---

## Overview

MindBridge connects your AI tools to *any* LLM provider — OpenAI, Anthropic, Google, DeepSeek, OpenRouter, Ollama, and OpenAI-compatible APIs — and lets them call each other for second opinions and multi-model workflows.

It can run in three modes:

| Mode | Transport | Typical clients |
|------|-----------|----------------|
| **MCP stdio** | stdin/stdout | Claude Desktop, Cursor, Windsurf |
| **HTTP/SSE** | `localhost:3000` | Claude.ai, ChatGPT Actions, Gemini Extensions |
| **Cloudflare Worker** | HTTPS | Any web client |

---

## Supported Providers

| Provider | Key variable |
|----------|-------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google AI | `GOOGLE_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Ollama (local) | `OLLAMA_BASE_URL` (default: `http://localhost:11434`) |
| OpenAI-compatible | `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_API_BASE_URL`, `OPENAI_COMPATIBLE_API_MODELS` |

---

## Installation

```bash
cd mindbridge
npm install
npm run build
```

---

## Running MindBridge

### MCP stdio (Claude Desktop / Cursor / Windsurf)

```bash
npm start
```

### HTTP server (Claude.ai / ChatGPT / Gemini)

```bash
npm run start:remote
# Development mode with hot-reload:
npm run dev:remote
```

The server starts on port 3000 by default. Set `PORT` and `BASE_URL` in `mindbridge/.env` for production.

### Cloudflare Worker

```bash
npm run worker:dev     # Local preview
npm run worker:deploy  # Deploy to Cloudflare
```

The Worker entrypoint is `mindbridge/src/remote-server.ts` (configured in `wrangler.jsonc`).

---

## MCP Configuration

Add to your `mcp.json` (Claude Desktop, Cursor, Windsurf):

```json
{
  "mcpServers": {
    "mindbridge": {
      "command": "npx",
      "args": ["-y", "@pinkpixel/mindbridge"],
      "env": {
        "OPENAI_API_KEY": "YOUR_KEY",
        "ANTHROPIC_API_KEY": "YOUR_KEY",
        "GOOGLE_API_KEY": "YOUR_KEY",
        "DEEPSEEK_API_KEY": "YOUR_KEY",
        "OPENROUTER_API_KEY": "YOUR_KEY"
      }
    }
  }
}
```

---

## Available Tools

### `getSecondOpinion`

Query any configured LLM provider.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | ✅ | Provider name (e.g. `openai`, `anthropic`, `google`) |
| `model` | string | ✅ | Model identifier |
| `prompt` | string | ✅ | The question or prompt |
| `systemPrompt` | string | — | Optional system instructions |
| `temperature` | number | — | Response randomness 0–1 |
| `maxTokens` | number | — | Maximum response length |
| `reasoning_effort` | `low`\|`medium`\|`high` | — | For reasoning-capable models |

### `listProviders`

Returns all configured providers and their available models. No parameters.

### `listReasoningModels`

Returns models optimised for reasoning tasks. No parameters.

### Agent Mesh tools

See [Agent Mesh](Agent-Mesh.md) for `registerVessel`, `listVessels`, `prepareAgentMigration`, `dispatchAgentMigration`, `listAgentMigrations`, and `announceAgentEvent`.

---

## HTTP Endpoints (remote mode)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sse` | GET | MCP over SSE (Claude.ai, MCP SuperAssistant) |
| `/messages` | POST | MCP client messages |
| `/api/tools/getSecondOpinion` | POST | REST — query a provider |
| `/api/tools/listProviders` | GET | REST — list providers |
| `/api/tools/listReasoningModels` | GET | REST — list reasoning models |
| `/openapi.json` | GET | OpenAPI spec (for GPT Actions) |
| `/health` | GET | Health check |

---

## REST API Example

```bash
# Query GPT-4o
curl -X POST http://localhost:3000/api/tools/getSecondOpinion \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "prompt": "What are the tradeoffs between microservices and monoliths?",
    "temperature": 0.7,
    "maxTokens": 1000
  }'

# List configured providers
curl http://localhost:3000/api/tools/listProviders
```

---

## Deployment Options

### Cloudflare Workers (recommended for public access)

```bash
cd mindbridge

# Add secrets (one-time)
wrangler secret put OPENAI_API_KEY
wrangler secret put ANTHROPIC_API_KEY

# Deploy
npm run worker:deploy
```

Your Worker URL: `https://mindbridge.<your-subdomain>.workers.dev`

### Render / Railway / Fly.io

- Build command: `npm run build`
- Start command: `npm run start:remote`
- Set `BASE_URL` to your public URL and add API key environment variables.

### Docker

```bash
docker build -t mindbridge-remote .
docker run -p 3000:3000 --env-file .env mindbridge-remote
```

### Local with ngrok

```bash
npm run start:remote
# In a separate terminal:
ngrok http 3000
# Use the ngrok HTTPS URL as BASE_URL
```

---

## Web AI Platform Integration

### Claude.ai

1. Deploy MindBridge to a publicly accessible HTTPS URL.
2. In Claude.ai: **Settings → Connectors → Add custom MCP server**.
3. URL: `https://your-url/sse` (SSE) or `/mcp` (Streamable HTTP).

### ChatGPT (GPT Actions)

1. Create a GPT at [chatgpt.com](https://chatgpt.com/gpts/editor).
2. Under **Actions**, set Schema URL to `https://your-url/openapi.json`.

### Gemini (Extensions)

1. Use Google AI Studio or Vertex AI to create an extension.
2. Point it to `https://your-url/api/tools/*` using the OpenAPI spec.

---

## Development Commands

```bash
npm run lint      # ESLint
npm run format    # Prettier
npm run clean     # Remove build artifacts
npm run build     # Compile TypeScript
```

---

## Version History

See [`mindbridge/CHANGELOG.md`](../mindbridge/CHANGELOG.md) for a full history.

- **1.2.0** — Agent Mesh architecture (experimental)
- **1.1.0** — Provider interface improvements, enhanced error handling
- **1.0.0** — Initial release: multi-provider LLM routing

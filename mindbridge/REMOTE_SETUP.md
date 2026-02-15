# MindBridge Remote Server — Setup for Claude.ai, ChatGPT, Gemini, Mistral

This guide explains how to run MindBridge as a remote HTTP server so your web-based AI chats (Claude.ai, ChatGPT, Gemini, Mistral) can call it.

---

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Configure API keys (edit .env with your keys)
cp .env.example .env

# 3. Build
npm run build

# 4. Start remote server
npm run start:remote
```

The server runs at `http://localhost:3000` by default. Set `PORT` and `BASE_URL` in `.env` for production.

---

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/sse` | GET | MCP over SSE (Claude.ai MCP Connector, MCP SuperAssistant) |
| `/messages` | POST | MCP client messages |
| `/api/tools/getSecondOpinion` | POST | REST API — get LLM response |
| `/api/tools/listProviders` | GET | REST API — list providers |
| `/api/tools/listReasoningModels` | GET | REST API — list reasoning models |
| `/openapi.json` | GET | OpenAPI spec (for GPT Actions) |
| `/health` | GET | Health check |

---

## Integration by Platform

### 1. Claude.ai (MCP Connector)

Claude.ai supports remote MCP servers via **Connectors** using Streamable HTTP or SSE.

1. Deploy MindBridge to a **publicly accessible URL** (Render, Railway, Fly.io, etc.).
2. In Claude.ai: **Settings → Connectors**.
3. Add a custom MCP server:
   - **URL**: `https://your-mindbridge-url.com/sse` (SSE) or `/mcp` (Streamable HTTP, if supported)
   - Configure auth if needed (Bearer token, etc.).

**Deployment:** The server must be reachable over HTTPS. Use a tunnel (ngrok, Cloudflare Tunnel) for local testing.

---

### 2. ChatGPT (GPT Actions)

ChatGPT GPTs can call MindBridge via **Actions** (OpenAPI).

1. Create a GPT at [chatgpt.com](https://chatgpt.com/gpts/editor).
2. Configure **Actions**:
   - Schema URL: `https://your-mindbridge-url.com/openapi.json`
   - Or paste the OpenAPI spec from `/openapi.json`.
3. Authentication: Use API Key or OAuth if you add auth to MindBridge.

**Example Action call:** The GPT can use `getSecondOpinion` to query another model.

---

### 3. Gemini (Extensions)

Google Gemini supports **Extensions** that call external APIs.

1. Use **Google AI Studio** or **Vertex AI** to create an extension.
2. Point to your MindBridge API: `https://your-mindbridge-url.com/api/tools/*`
3. Configure the extension with the OpenAPI spec from `/openapi.json`.

---

### 4. Mistral

Mistral supports **tools** via API. You can:

- Call MindBridge REST API from your own app that uses Mistral’s API.
- Or configure Mistral’s tool-calling to hit your MindBridge endpoints.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PORT` | Server port (default: 3000) |
| `BASE_URL` | Public URL for OpenAPI spec (e.g. `https://mindbridge.example.com`) |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GOOGLE_API_KEY` | Google AI API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OLLAMA_BASE_URL` | Ollama URL (default: http://localhost:11434) |

---

## Deployment

### Cloudflare Workers (recommended)

```bash
# Install deps (includes wrangler)
npm install

# Add API keys as secrets (one-time)
wrangler secret put OPENAI_API_KEY
wrangler secret put ANTHROPIC_API_KEY
# Optional: GOOGLE_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY

# Local dev
npm run worker:dev

# Deploy
npm run worker:deploy
```

Your Worker will be live at `https://mindbridge.<your-subdomain>.workers.dev`. Use that URL for Claude.ai, ChatGPT Actions, etc.

### Render / Railway / Fly.io

1. Set build command: `npm run build`
2. Set start command: `npm run start:remote`
3. Add env vars for API keys and `BASE_URL` (your public URL).

### Local with ngrok

```bash
npm run start:remote
# In another terminal:
ngrok http 3000
# Use the ngrok URL as BASE_URL
```

### Docker

```bash
docker build -t mindbridge-remote .
docker run -p 3000:3000 --env-file .env mindbridge-remote
```

---

## REST API Example

```bash
# Get second opinion from GPT-4o
curl -X POST http://localhost:3000/api/tools/getSecondOpinion \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "prompt": "What are the tradeoffs between microservices and monoliths?",
    "temperature": 0.7,
    "maxTokens": 1000
  }'

# List providers
curl http://localhost:3000/api/tools/listProviders
```

---

## Security Notes

- Add authentication (API key, OAuth) before exposing publicly.
- Use HTTPS in production.
- Rate limiting is recommended for public endpoints.

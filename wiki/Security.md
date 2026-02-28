# Security

This page describes the security model for SoulSpace and best-practice recommendations.

---

## Single-User Design

> ⚠️ **SoulSpace is intentionally a single-user system.** The `/exec` and `/shell` commands allow arbitrary code execution on the host machine. Never expose your Discord server to untrusted users.

---

## Code Execution Security

The `/exec` and `/shell` commands execute code directly on the host. The following mitigations are in place:

| Mitigation | Details |
|-----------|---------|
| **Command blacklist** | `/shell` rejects known-dangerous commands before execution |
| **30-second timeout** | Prevents runaway processes from hanging the bot |
| **Trace logging** | Every execution is recorded in Notion with a trace ID |
| **Error channel** | Failures are immediately posted to `#the-scream` for visibility |

### Recommendations

- Run Calyx under a **low-privilege OS user account** — it should not have root or sudo access.
- Run in a **sandboxed environment** (Docker container, VM, or restricted network namespace).
- Do not expose your Discord server to untrusted users.
- Review `logs/calyx.log` and the Notion Trace Log regularly for unexpected executions.

---

## API Key Security

All API keys (Discord, Notion, Google, LLM providers) are loaded from environment variables via `.env`.

- `.env` is listed in `.gitignore` — **never commit it to version control**.
- The `.env.example` file contains only placeholder values and is safe to commit.
- MindBridge API keys are kept in `mindbridge/.env`, also gitignored.

---

## Google OAuth

- OAuth credentials are stored locally as token files (`token_gmail.json`, `token_calendar.json`).
- These files should be kept private and not committed.
- If credentials are compromised, revoke them in [Google Cloud Console](https://console.cloud.google.com/) and delete the local token files.

---

## MindBridge HTTP Server

When running MindBridge in HTTP or Cloudflare Worker mode and exposing it to the public internet:

- **Add authentication** (API key or OAuth) before going public.
- **Use HTTPS** in production (Cloudflare Workers provide this automatically).
- **Enable rate limiting** to prevent abuse of LLM API quotas.
- Keep API keys as Cloudflare Worker **secrets** (not hardcoded in `wrangler.jsonc`):
  ```bash
  wrangler secret put OPENAI_API_KEY
  ```

---

## Health Endpoint

The health server (`port 8080`) is bound to `0.0.0.0` by default. If Calyx is running on a network-accessible host, consider:

- Binding to `127.0.0.1` instead (edit `health_server.py`).
- Placing the port behind a firewall or reverse proxy.

---

## Dependency Security

- Keep Python and Node.js dependencies up to date.
- Run `pip list --outdated` and `npm outdated` periodically.
- Review the `requirements.txt` and `mindbridge/package.json` for known vulnerabilities.

---

## Responsible Use

SoulSpace handles personal data (memories, knowledge entries, task history). Ensure:

- Notion databases are not shared publicly.
- The Discord server is kept private.
- The Memory Archive retention policies are set appropriately for your data.

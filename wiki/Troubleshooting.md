# Troubleshooting

Common issues and how to resolve them.

---

## Bot Won't Start

### Symptom
`calyx.py` exits immediately or throws an error before connecting to Discord.

### Checks

1. **Missing environment variables** — Make sure `.env` is present and all required fields are filled in:
   ```bash
   cat .env | grep -v "^#" | grep -v "^$"
   ```

2. **Invalid Discord token** — Regenerate the token in the Discord Developer Portal and update `DISCORD_TOKEN`.

3. **Python version** — Calyx requires Python 3.10+:
   ```bash
   python --version
   ```

4. **Missing dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Notion authentication failed** — Check the console for `Notion auth failed`. Verify that `NOTION_TOKEN` is correct and not expired.

---

## Commands Not Appearing

### Symptom
Slash commands are not listed in Discord after the bot starts.

### Checks

- Ensure the bot was invited with the `applications.commands` scope (see [Installation and Configuration](Installation-and-Configuration.md)).
- Slash command registration can take up to **1 hour** to propagate globally. For instant registration in a single server, use guild-scoped commands during development.
- Check the console for errors during command tree sync.

---

## Schema Validation Failures

### Symptom
Startup output shows ❌ errors for one or more databases.

### Fixes

| Error | Action |
|-------|--------|
| `Database ID not configured` | Add the missing `NOTION_*_ID` variable to `.env` |
| `Missing required property 'X'` | Add the property to the Notion database with the exact name and type |
| `Property 'X' has wrong type` | Delete and re-create the property with the correct type |
| `Property name case mismatch` | Rename the property in Notion to match exactly (case-sensitive) |
| `API error` | Check `NOTION_TOKEN` is valid and the database is shared with the integration |

See [Notion Databases](Notion-Databases.md) for the full expected schemas.

---

## OAuth Callback Timeout

### Symptom
Running `/auth gmail` or `/auth calendar` opens a browser but the callback never completes.

### Checks

1. **Port blocked** — Make sure `OAUTH_REDIRECT_PORT` (default `9090`) is open in your firewall.
2. **Browser didn't open** — Copy the URL from the bot's response and open it manually.
3. **Credentials expired** — Delete the stored token file and re-run `/auth <service>`.
4. **Wrong redirect URI** — In Google Cloud Console, ensure `http://localhost:9090` is listed as an authorised redirect URI for your OAuth client.

---

## Agent Health Not Updating

### Symptom
The Agent Health Monitor database in Notion is not being updated.

### Checks

1. `NOTION_AGENT_HEALTH_ID` is set correctly.
2. The database schema matches the expected schema (see [Notion Databases](Notion-Databases.md)).
3. Check `logs/errors.log` for `Failed to update agent health` messages.
4. Verify the integration has write access to the database.

---

## Trace Logs Missing

### Symptom
Traces are not appearing in the Notion Trace Log Index.

### Checks

1. `NOTION_TRACE_LOG_ID` is set correctly.
2. The database has all required properties (especially `Trace ID` as the title field).
3. Check `logs/errors.log` for `Failed to log trace` messages.

---

## Health Endpoint Returns 503

### Symptom
`GET http://localhost:8080/health/ready` returns `503`.

### Checks

- **Discord not ready** — The bot may still be connecting. Wait 10–15 seconds and retry.
- **Notion check failing** — `NOTION_TOKEN` may be invalid or the Notion API may be temporarily unavailable.

---

## MindBridge Issues

### Server Won't Start

```bash
# Check Node.js version (requires 18+)
node --version

# Rebuild
cd mindbridge
npm install
npm run build
```

### Provider Not Configured

If `getSecondOpinion` returns `Provider "X" not configured`:

- Check that the API key variable for that provider is set in `mindbridge/.env`.
- Restart MindBridge after editing the environment file.

### Cloudflare Worker Deployment Fails

```bash
# Authenticate wrangler
wrangler login

# Check configuration
cat mindbridge/wrangler.jsonc

# Redeploy
npm run worker:deploy
```

---

## Log File Reference

| File | Content |
|------|---------|
| `logs/calyx.log` | Full debug log |
| `logs/errors.log` | Errors only |
| Console output | INFO-level summary |

---

## Still Stuck?

1. Search existing issues: https://github.com/harbz07/SoulSpace/issues
2. Join the Discord server: https://discord.gg/QU7urpGV
3. Open a new issue with the relevant log output.

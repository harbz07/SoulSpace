# Health and Monitoring

Calyx exposes a built-in HTTP health server and structured log files to support monitoring and observability.

---

## Health Server

The health server is implemented in `health_server.py` using `aiohttp` and runs on port **8080** alongside the Discord bot.

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic service status |
| `/health/live` | GET | Kubernetes-style liveness probe |
| `/health/ready` | GET | Kubernetes-style readiness probe |
| `/metrics` | GET | Basic runtime metrics |

---

### `GET /health`

Returns service identification and uptime.

```json
{
  "status": "healthy",
  "service": "Calyx",
  "timestamp": "2026-02-27T06:00:00.000Z",
  "uptime_seconds": 3600.0
}
```

---

### `GET /health/live`

Checks whether the Discord connection is open. Returns `503` if the bot has disconnected.

```json
{ "status": "alive" }
```

On failure:

```json
{ "status": "unhealthy", "reason": "Bot connection closed" }
```

---

### `GET /health/ready`

Checks both Discord connectivity and the Notion API connection.

```json
{
  "status": "ready",
  "checks": {
    "discord": true,
    "notion": true
  }
}
```

Returns `503` if any check fails.

---

### `GET /metrics`

Returns runtime counters.

```json
{
  "uptime_seconds": 3600.0,
  "discord_latency_ms": 42.1,
  "guild_count": 1,
  "user_count": 5,
  "notion_connected": true
}
```

---

## Logging

Calyx uses Python's built-in `logging` module with file rotation, configured in `calyx.py`.

### Log Files

| File | Level | Details |
|------|-------|---------|
| `logs/calyx.log` | DEBUG+ | Full structured log with function names and line numbers |
| `logs/errors.log` | ERROR+ | Errors only |

Both files rotate at **10 MB** with **5 backups** kept.

### Log Format

**Console:**
```
HH:MM:SS | LEVEL | message
```

**File:**
```
YYYY-MM-DD HH:MM:SS | logger_name | LEVEL | function:line | message
```

### Log Levels

| Level | Used for |
|-------|---------|
| DEBUG | Detailed trace data (file only) |
| INFO | Normal operations and startup messages |
| WARNING | Non-fatal issues (e.g. schema case mismatches) |
| ERROR | Failures written to both `errors.log` and Discord `#the-scream` |

---

## Trace System

Every significant operation is assigned a **Trace ID** — a UUID prefixed with `TRACE-`:

```
TRACE-550e8400-e29b-41d4-a716-446655440000
```

Traces are:

- Posted to the `#engine-logs` Discord channel.
- Written to the Notion **Trace Log Index** database.
- Retrievable with the `/trace <trace_id>` slash command.

---

## Schema Validation on Startup

`notion_validator.py` runs at startup and checks every Notion database schema. Results are printed to the console and logged:

```
======================================================================
NOTION DATABASE SCHEMA VALIDATION
======================================================================
✅ Task Board: Schema validation passed
✅ Trace Log Index: Schema validation passed
⚠️  Agent Health Monitor: Schema validation passed with warnings
❌ Knowledge Base: Schema validation FAILED
❌ Knowledge Base: Missing required property 'Consent Level'
✅ Memory Archive: Schema validation passed
======================================================================
⚠️  Some databases have schema issues - bot will continue but may encounter errors
======================================================================
```

---

## Monitoring Recommendations

- Monitor `/health/ready` with an external uptime checker (e.g. UptimeRobot, Grafana).
- Route the `#the-scream` Discord channel to a notification system for real-time error alerts.
- Review `logs/errors.log` periodically for recurring issues.
- Use Notion's built-in views on the **Agent Health Monitor** database to spot agents with high error counts.

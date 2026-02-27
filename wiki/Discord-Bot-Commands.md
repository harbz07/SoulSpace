# Discord Bot Commands

All commands are Discord slash (`/`) commands. Calyx is a **single-user system** — only share your Discord server with trusted users.

---

## System Control

### `/pause`

Suspends all automated triggers. Manual commands still work.

### `/resume`

Re-enables automated operations that were suspended with `/pause`.

---

## Information & Debugging

### `/status`

Shows the current health of all registered agents, including:
- Agent name
- Status (Active / Paused / Error / Disabled)
- Last execution timestamp
- Error count

### `/trace <trace_id>`

Retrieves the raw log entries associated with a specific Trace ID.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `trace_id` | string | The trace identifier to look up (e.g. `TRACE-1234567890`) |

---

## Code Execution

> ⚠️ **These commands allow arbitrary code execution. Only use them on a single-user server you control.**

### `/exec <code>`

Execute a Python code snippet directly on the host machine.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | string | Python code to execute |

- **Timeout:** 30 seconds
- Output is returned to the Discord channel.
- Failures are posted to `#the-scream`.
- Every execution is logged with a trace ID.

### `/shell <command>`

Execute a shell command on the host machine.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | string | Shell command to execute |

- **Timeout:** 30 seconds
- A **command blacklist** prevents known-dangerous commands.
- Output is returned to the Discord channel.
- All executions are logged with a trace ID.

---

## Authentication

### `/auth <service>`

Initiate an OAuth flow for an external service.

**Parameters:**

| Parameter | Type | Options |
|-----------|------|---------|
| `service` | string | `gmail`, `calendar` |

A browser window opens for the OAuth consent screen. On success, credentials are stored locally for subsequent API calls.

---

## Data Management

### `/export`

Generates a full data dump of Notion databases for offline backup. The dump is returned as a file attachment in Discord.

### `/purge <memory_id>`

Permanently deletes a specific memory entry from the Notion Memory Archive.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `memory_id` | string | The Memory ID to delete |

> ⚠️ This action is irreversible.

---

## Startup Behaviour

When Calyx starts it automatically:

1. Posts a startup message to `#the-mirror` with current agent health.
2. Runs schema validation and logs any issues.
3. Begins listening for commands and events.

---

## Logging

All commands produce structured log entries:

- Console output (INFO level)
- `logs/calyx.log` — full debug log (10 MB rotation, 5 backups)
- `logs/errors.log` — errors only
- Notion Trace Log Index — every operation with its trace ID

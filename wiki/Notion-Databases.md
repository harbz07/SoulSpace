# Notion Databases

Calyx uses five Notion databases as its persistent memory layer. All five must be created, configured with the correct property schemas, and shared with your Notion integration before starting the bot.

---

## Schema Validation

On every startup, `notion_validator.py` checks each database against its expected schema and logs results:

| Symbol | Meaning |
|--------|---------|
| ✅ | Property exists with the correct type |
| ⚠️ | Property name has a case mismatch |
| ❌ | Property missing or wrong type |
| ℹ️ | Extra (unexpected) properties found — informational only |

If any database has ❌ errors the bot will still start, but operations that write to that database may fail.

---

## 1. Task Board

**Environment variable:** `NOTION_TASK_BOARD_ID`

Tracks all tasks and their lifecycle.

| Property | Type | Valid values |
|----------|------|-------------|
| `Task` | title | — |
| `Status` | select | To-Do, Executing, Blocked, Done, Cancelled |
| `Priority` | select | Critical, High, Medium, Low |
| `Assigned To` | select | tinyNature, Calyx, Harvey, Claude, Other |
| `Trigger Source` | select | Manual, TIME, EVENT, API |
| `Trace Link` | url | — |
| `Blocker Reason` | rich_text | — |

---

## 2. Trace Log Index

**Environment variable:** `NOTION_TRACE_LOG_ID`

Records execution traces for every operation so that debugging is always possible.

| Property | Type | Description |
|----------|------|-------------|
| `Trace ID` | title | Unique trace identifier (e.g. `TRACE-<uuid>`) |
| `Timestamp` | date | UTC time of the operation |
| `Request Summary` | rich_text | What was requested (first 200 characters) |
| `Agent Chain` | rich_text | Sequence of agents invoked (e.g. `tinyNature → Calyx`) |
| `Data Sources Used` | multi_select | APIs and databases consulted |
| `Discord Link` | url | Jump URL to the original Discord message |
| `Success` | checkbox | Whether the operation completed successfully |

---

## 3. Agent Health Monitor

**Environment variable:** `NOTION_AGENT_HEALTH_ID`

Tracks runtime health for each registered agent.

| Property | Type | Valid values |
|----------|------|-------------|
| `Agent Name` | title | — |
| `Status` | select | Active, Paused, Error, Disabled |
| `Last Execution` | date | — |
| `Execution Count` | number | — |
| `Error Count` | number | — |
| `Last Error Message` | rich_text | — |
| `Auth Status` | select | Valid, Expired, Invalid, N/A |

Calyx upserts (update or create) health records using the agent name as the key.

---

## 4. Knowledge Base

**Environment variable:** `NOTION_KNOWLEDGE_BASE_ID`

Stores verified, categorised information entries.

| Property | Type | Description |
|----------|------|-------------|
| `Entry Title` | title | Short title for the knowledge entry |
| `Category` | select | Arbitrary category label |
| `Consent Level` | select | Access / sharing consent level |
| `Source` | select | Where the information came from |
| `Last Verified` | date | When this entry was last confirmed accurate |

---

## 5. Memory Archive

**Environment variable:** `NOTION_MEMORY_ARCHIVE_ID`

Long-term memory storage with retention and consent management.

| Property | Type | Description |
|----------|------|-------------|
| `Memory ID` | title | Unique memory identifier |
| `Type` | select | Type of memory |
| `Consent Status` | select | Current consent status |
| `Created Date` | date | When the memory was created |
| `Last Accessed` | date | Most recent access timestamp |
| `Access Count` | number | Total number of accesses |
| `Retention Policy` | select | How long to retain this memory |
| `Content Preview` | rich_text | Short preview of the memory content |

---

## Optional: The Glass Journal

**Environment variable:** `JOURNAL_DB_ID`

An optional broadcast database used for journal-style updates. Not required for core functionality.

---

## Getting Database IDs

1. Open the database in Notion in **full-page view** (not inline).
2. Copy the URL from your browser — it looks like:
   ```
   https://notion.so/workspace/<DATABASE_ID>?v=<VIEW_ID>
   ```
3. Extract the 32-character hex `DATABASE_ID` (between the last `/` and the `?`).
4. Paste it into the corresponding variable in `.env`.

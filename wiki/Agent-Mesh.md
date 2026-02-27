# Agent Mesh

> **Status: Experimental.** The Agent Mesh feature is available but may change in future releases.

Agent Mesh extends MindBridge from an LLM router into an **agent handoff coordinator** for vessel-hosted runtimes.

---

## Concepts

| Term | Definition |
|------|-----------|
| **Vessel** | A host runtime (server, worker, or process) that can receive migrating agents |
| **Migration** | A signed, time-limited package that moves an agent's state from one vessel to another |
| **Agent** | A logical task runner (e.g. Calyx) that can be serialised and resumed elsewhere |

---

## What Agent Mesh Enables

- Register vessel hosts as migration targets.
- Prepare migration packages with a checksum and expiry.
- Dispatch migration payloads to remote vessel HTTP endpoints.
- Broadcast migration outcomes to Discord webhooks and forum threads.

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `registerVessel` | Register or update a vessel host in the mesh |
| `listVessels` | List known vessels with capabilities and endpoints |
| `prepareAgentMigration` | Create a migration package with checksum and TTL |
| `dispatchAgentMigration` | Send a prepared package to the target vessel |
| `listAgentMigrations` | Query migration history by status |
| `announceAgentEvent` | Send a status update to a Discord webhook or forum |

---

## Suggested Workflow

```
1. Register vessels
   registerVessel(vesselId="vessel-alpha", baseUrl="https://…")
   registerVessel(vesselId="vessel-beta",  baseUrl="https://…")

2. Prepare a migration package
   prepareAgentMigration(
     agentId="calyx",
     sourceVesselId="vessel-alpha",
     targetVesselId="vessel-beta",
     state={ task: "resume orchestration", traceId: "trace-123" },
     ttlSeconds=1200
   )

3. Dispatch the migration
   dispatchAgentMigration(migrationId="<id>")

4. Monitor status
   listAgentMigrations(status="completed")

5. (Optional) Broadcast outcome
   announceAgentEvent(
     content="Calyx migrated to vessel-beta",
     threadName="calyx-runtime"
   )
```

---

## Target Vessel Contract

`dispatchAgentMigration` posts JSON to the target vessel:

- **Default path:** `/migrations/ingest`
- Overridable per vessel via the `migrationEndpointPath` field.
- Optional bearer auth with `MINDBRIDGE_MIGRATION_AUTH_TOKEN`.

### Example payload

```json
{
  "migrationId": "0bfe9510-44f8-4db9-8e82-2ab16ae26b7f",
  "agentId": "calyx",
  "sourceVesselId": "vessel-alpha",
  "targetVesselId": "vessel-beta",
  "checksum": "sha256:…",
  "memoryRefs": ["notion://memory/abc123"],
  "createdAt": "2026-02-21T20:00:00.000Z",
  "expiresAt": "2026-02-21T20:15:00.000Z",
  "state": {
    "task": "resume orchestration",
    "traceId": "trace-123"
  }
}
```

---

## Configuration

| Variable | Description |
|----------|-------------|
| `MINDBRIDGE_AGENT_MESH_STORAGE_PATH` | Path to a JSON file for persisting vessel and migration state. If omitted, state is in-memory only. |
| `MINDBRIDGE_MIGRATION_ENDPOINT_PATH` | Default vessel handoff path (default: `/migrations/ingest`) |
| `MINDBRIDGE_MIGRATION_AUTH_TOKEN` | Optional bearer token added to migration dispatch requests |
| `MINDBRIDGE_DISCORD_WEBHOOK_URL` | Default Discord webhook for migration/event announcements |
| `MINDBRIDGE_DISCORD_FORUM_WEBHOOK_URL` | Default Discord forum webhook for threaded announcements |

---

## Discord Announcements

- **Standard webhook** — posts to a normal channel.
- **Forum webhook** — posts with `thread_name` to create or use a forum thread.
- `dispatchAgentMigration` can auto-announce outcomes using the defaults above or per-vessel webhook overrides.

---

## Persistence

Without `MINDBRIDGE_AGENT_MESH_STORAGE_PATH`, all vessel and migration state is **lost when the process restarts**.

Set this variable to a file path (e.g. `/tmp/mindbridge-agent-mesh.json`) to persist state across restarts.

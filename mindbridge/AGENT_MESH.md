# MindBridge Agent Mesh (Experimental)

Agent Mesh extends MindBridge from "LLM router" to "agent handoff coordinator" for vessel-hosted runtimes.

## What this enables

- Register vessel hosts as migration targets
- Prepare migration packages with checksum + expiry
- Dispatch migration payloads to remote vessel endpoints
- Broadcast migration outcomes to Discord webhooks and forum webhooks

## MCP Tools

1. `registerVessel`
2. `listVessels`
3. `prepareAgentMigration`
4. `dispatchAgentMigration`
5. `listAgentMigrations`
6. `announceAgentEvent`

## Suggested flow

1. Register source and target vessels:
   - `registerVessel(vessel-alpha)`
   - `registerVessel(vessel-beta)`
2. Prepare handoff package:
   - `prepareAgentMigration(agentId="calyx", source="vessel-alpha", target="vessel-beta", state={...})`
3. Dispatch:
   - `dispatchAgentMigration(migrationId="...")`
4. Observe:
   - `listAgentMigrations(status="completed")`
5. Broadcast extra events:
   - `announceAgentEvent(content="Forum sync complete", threadName="calyx-runtime")`

## Target vessel contract

`dispatchAgentMigration` posts JSON to the target vessel endpoint:

- Default path: `/migrations/ingest`
- Overridable per vessel (`migrationEndpointPath`)
- Optional bearer auth with `MINDBRIDGE_MIGRATION_AUTH_TOKEN`

### Example payload

```json
{
  "migrationId": "0bfe9510-44f8-4db9-8e82-2ab16ae26b7f",
  "agentId": "calyx",
  "sourceVesselId": "vessel-alpha",
  "targetVesselId": "vessel-beta",
  "checksum": "sha256...",
  "memoryRefs": ["notion://memory/abc123"],
  "createdAt": "2026-02-21T20:00:00.000Z",
  "expiresAt": "2026-02-21T20:15:00.000Z",
  "state": {
    "task": "resume orchestration",
    "traceId": "trace-123"
  }
}
```

## Persistence

Set `MINDBRIDGE_AGENT_MESH_STORAGE_PATH` to persist:

- Vessel registry
- Migration package state

If omitted, mesh state is in-memory only for that process lifecycle.

## Discord webhook/forum notes

- Standard webhook: post to a normal channel
- Forum webhook: post with `thread_name` to create/use a forum thread
- `dispatchAgentMigration` can auto-announce outcomes using defaults from env or per-vessel webhook settings

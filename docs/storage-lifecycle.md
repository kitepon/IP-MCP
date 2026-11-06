# Storage ownership and data flow

This is the capacity detail of the [README architecture](../README.md) and [PLAN](../PLAN.md). It maps the existing single-process server and the planned bounded access log change before implementation. No cross-source fallback is introduced.

## Feature map

| Function | Implementation | Input → output / ownership |
|---|---|---|
| Serve MCP and OAuth | `server.create_server`, `server.main`, `auth/provider.SqliteOAuthProvider` | Client requests → authenticated MCP responses. `data/oauth.db` owns durable registrations and tokens; keep it across image replacement. |
| Obtain official data | `tools_official/*`, `jpo/client.JpoClient` | Patent identifiers → JPO JSON, in-memory ZIP bytes or signed URLs. No disk document cache is implemented. |
| Search unofficial data | `tools_external/google_patents_search.py` | Search terms → independently labeled Google results. No disk result cache. |
| Record calls | `access_log.log_call`, `_get_handle` | Result metadata → `ACCESS_LOG_PATH` (default `/app/logs/access.jsonl`). Planned: rotate before the next record when the active file plus that record exceeds 10 MiB; retain `.1` and `.2`. A single record can exceed the threshold. Same lock covers rotation and writing. |
| Summarize calls | `scripts/summarize_logs.main` | Retained `.2`, `.1`, active JSONL → quota/error summaries filtered by `--days`. The time window can exceed retained history; report only available records. |
| Build and deploy | `Dockerfile`, `docker-compose.yml` | Tracked source and dependencies → runtime image, with pip/uv caches disabled. `cache`, `logs`, `data` remain bind mounts. Host-specific approved deployment, NAS backup and image retention use the host operator's canonical deployment runbook. |

## Data-flow map

| Flow | Producer → processing → consumer/store | Failure and lifetime |
|---|---|---|
| F1 OAuth | MCP client → OAuth provider ↔ `data/oauth.db` → MCP client | Durable sole state. Capacity maintenance does not delete rows or replace the DB. |
| F2 official | MCP client → official tools → JPO → official tools → MCP client | Source labels stay official; failures stay with that source. Documents are memory responses, not saved files. |
| F3 unofficial | MCP client → external search → Google → external search → MCP client | Separate source labels and retry behavior; no fallback from F2. |
| F4 log write | F2/F3 result metadata → `log_call` → JSONL files | Original behavior is unlimited append; this change bounds retained generations. Open/write/rotation failures warn without breaking the API response. Process termination may interrupt the last record; the reader counts malformed lines. |
| F5 log read | Retained JSONL generations → `summarize_logs` → operator | Read oldest to newest so the latest quota value wins. Concurrent file replacement can remove a generation before open; skip only FileNotFoundError, surface other errors. |
| F6 host update | Approved image IDs + current DB → maintainer deployment → Docker/NAS + verification receipts | Current/rollback images and current DB preserved. NAS mismatch prevents deployment. Host policy is owned in the maintainer's canonical operations, not duplicated here. |

The runtime log is operational history, not a permanent audit archive. Rotation discards the oldest generation after two backups. Docker stdout/stderr rotation is a separate host/Compose setting. Existing OAuth data and required NAS backup generations have independent retention.

Build context contract: `.dockerignore` excludes credentials (`.env*`), runtime `data/logs/cache`, Git, development environments, bytecode and generated build/test caches. Only source/build metadata and tests needed by Docker targets remain eligible. Runtime bind mounts and backup data never become build input. Docker builder cache remains owned by the host operator.

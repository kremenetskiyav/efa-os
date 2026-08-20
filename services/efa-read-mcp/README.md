# EFA Read MCP v1

`EFA Read MCP` is a closed, read-only adapter between an MCP host and the seven curated PostgreSQL views in `mcp_read`. It exposes eight task-specific tools plus one bounded analytics tool. It exposes no resource, prompt, connection-management, arbitrary-schema, or write capability.

## Runtime contract

- Python 3.13.13 in the container.
- Official Python MCP SDK `mcp==2.0.0` (stable v2 release).
- `asyncpg==0.31.0` and `pydantic==2.13.4`.
- PostgreSQL AST parsing through `pglast==8.4`; analytics validation is not regex-based.
- stdio transport only in v1; stdout is reserved for MCP protocol frames.
- `DATABASE_URL` is accepted only from the process environment and must target database `efa` as role `efa_mcp_readonly`.
- The SQLAlchemy-style `postgresql+asyncpg://` prefix is normalized in memory for asyncpg. The URL is never logged.

## Exactly nine tools

| Tool | Fixed source | Bound |
| --- | --- | --- |
| `list_products` | `mcp_read.product_overview` | all compact product identities; archived excluded by default |
| `get_product_overview` | `mcp_read.product_overview` | at most one exact `offer_id` |
| `get_price_history` | `mcp_read.product_price_history` | 366 days, 500 rows |
| `get_stock_history` | `mcp_read.product_stock_history` | 366 days, 500 rows |
| `get_daily_performance` | `mcp_read.product_daily_performance` | 366 days, 500 rows |
| `get_region_logistics` | `mcp_read.product_region_logistics` | 200 rows |
| `get_promotion_state` | `mcp_read.product_promotion_state` | exact `offer_id` |
| `get_cpc_daily` | `mcp_read.product_cpc_daily` | 366 days, 500 rows |
| `query_analytics` | only AST-validated references to `mcp_read.*` | 200 rows by default, 500 maximum |

The first eight statements are fixed, schema-qualified, parameterized `SELECT` queries. CPC filtering deliberately retains ACCOUNT rows as `offer_id=null` and never synthesizes product facts. `query_analytics` accepts exactly one PostgreSQL `SELECT` or `WITH ... SELECT`, validates its AST, requires all base relations to be explicitly qualified in `mcp_read`, rejects write/control/locking operations, and applies an outer server-side row bound. All nine top-level input schemas are closed and reject unknown arguments. A narrow compatibility guard is retained while the pinned MCP SDK 2.0.0 generates permissive argument models; contract tests fail if that SDK behavior or its internal hook changes.

## Security boundary

PostgreSQL ACLs on `efa_mcp_readonly` are the primary control. The application adds a small connection pool, a read-only transaction per call, statement and lock timeouts, strict request models, safe row limits, and masked errors. Analytics queries always use a 10-second statement timeout and 3-second lock timeout. Null values stay null. Ordered demand and delivered economics remain separate. Quality, freshness, confidence, and collection status fields are returned rather than hidden.

Audit logs contain only tool name, duration, row count, success/failure, and correlation ID. Do not add request parameters, database rows, SQL errors, or environment values to logs.

## Local configuration

Use `.env.example` only as a list of accepted names. Never write a real URL into a tracked file. The local launcher accepts the credential only from this predetermined, untracked, access-controlled file:

```text
C:\Users\Andrey\.efa-os\secrets\efa-read-mcp.env
```

The file is not created by this repository. It must contain exactly one non-comment setting, `DATABASE_URL`, for `efa_mcp_readonly` only. It must not contain EFA OS admin credentials or optional runtime settings. Provision it later using an approved secret-handling procedure and restrict its Windows ACL to the intended user and system administrators.

Prepare an isolated interpreter later at `services/efa-read-mcp/.venv` and install the pinned requirements into it. The launcher deliberately has no fallback to a global interpreter or another credential source. It resolves every runtime path from its own location, never prints `DATABASE_URL`, runs stdio, restores the parent environment, and returns the MCP process exit code.

Manual registration parameters for a local command-based ChatGPT MCP entry:

```text
Name: EFA_READ_MCP
Command: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
Arguments: -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File D:\efa-os-github\services\efa-read-mcp\run-local.ps1
Working directory: not required
Environment: none
```

Do not place `DATABASE_URL` in the registration Environment field. `run-local.ps1` reads it only from the protected file and starts `python -m efa_read_mcp` over stdio. The process does not open an HTTP port.

## Docker build and tests

From the repository root, use the service directory as the build context so local files elsewhere in the repository are never sent to the Docker builder:

```text
docker build --file services/efa-read-mcp/Dockerfile --target test --tag efa-read-mcp:test services/efa-read-mcp
docker run --rm efa-read-mcp:test
docker build --file services/efa-read-mcp/Dockerfile --target runtime --tag efa-read-mcp:local services/efa-read-mcp
```

The runtime image has a non-root user, no package manager additions, no credentials, no host mount, no Docker socket, and no published port. A launcher should limit memory/CPU and attach only the database network when Docker deployment is explicitly approved.

## Deployment options (not applied here)

1. The prepared local stdio launcher reads the dedicated MCP URL from the fixed protected file, places it only in the child environment, and connects through the host route encoded in that URL. Credential provisioning and MCP registration remain separate approved steps.
2. A Docker MCP Gateway custom catalog entry could launch the image on `efa-tools` and inject the keychain secret into `DATABASE_URL`. This is acceptable only if the Gateway manifest supports both secret binding and joining the existing `efa-tools` network without exposing Docker control or broad outbound access.

Do not add a plaintext fallback. Do not deploy a long-running container or edit an MCP profile without separate approval.

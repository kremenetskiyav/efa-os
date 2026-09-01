# EFA OS Control Center v1

Small read-only panel for the existing Timeweb runtime. It serves one HTML
screen, reads the completed AI Analyst report, reads the existing Analyst cron
schedule and uses the existing `efa_mcp_readonly` PostgreSQL role. It does not
write to PostgreSQL, n8n, Ozon or collector services.

The static `/capabilities` page is an operator reference built from the
2026-09-01 READ-ONLY capabilities audit and the canonical Ozon Discount &
Points Settlement Contract v1. It contains the 30-item maturity catalog and 15
daily owner commands. It does not query live financial data, recalculate
economics or expose a write action.

`capabilities.json` is a `STATIC SNAPSHOT` dated 2026-09-01, not a live runtime
feed or an independent source of truth. Its canonical provenance remains the
`EFA OS — Current Capabilities & Ready Agents Inventory` audit, runtime evidence,
repository contracts and
`docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md`.

Runtime inputs:

- `/var/log/efa-os/ai-analyst-latest.txt`
- `/var/log/efa-os/ai-analyst-email.log`
- `/etc/cron.d/efa-os-analytics`
- `DATABASE_URL` for `efa_mcp_readonly`
- local n8n and EFA Read MCP ports

Run locally:

```text
python services/control-center/app.py --host 127.0.0.1 --port 8090
```

Production uses one systemd service and listens only on `127.0.0.1:8090`.
Caddy provides HTTPS and Basic Auth at `panel.efa-os.ru`.
The protected Control Center environment file retains the existing read-only
DSN and uses `127.0.0.1` for the host-side PostgreSQL connection.

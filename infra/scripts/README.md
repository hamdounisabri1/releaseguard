# infra/scripts/

| Script | What | Ticket |
|---|---|---|
| [`webhook_echo.py`](webhook_echo.py) | Development stand-in for `POST /api/v1/github/webhooks` on `127.0.0.1:8000`: checks the HMAC on the raw bytes and logs only metadata. Used with the smee tunnel until the real endpoint exists. Steps: [GITHUB_APP_SETUP.md § Run the webhook tunnel](../../docs/GITHUB_APP_SETUP.md#run-the-webhook-tunnel) | SCRUM-9 |

> **Coming later.** `backup.sh` (nightly `pg_dump`, retention, off-host copy), `restore.sh` and the deploy script arrive in SCRUM-97 (Sprint 6). See [infra.md](../../.claude/rules/infra.md).

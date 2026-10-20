# Automation and server deployment

## Daily commands

| Goal | Command |
|---|---|
| Start everything (Docker DB + API + UI, auto-generates secrets on first run, opens browser) | VS Code task **SecureVault: Start**, or `powershell -File scripts/start-securevault.ps1` |
| Full quality gate (ruff, pytest, node tests, mypy, pip-audit) | `python scripts/check.py` |
| Fast gate (what the pre-commit hook runs) | `python scripts/check.py --fast` |
| Enable pre-commit hook manually | `python scripts/check.py --install-hooks` (the start script also does this) |

CI (`.github/workflows/ci.yml`) runs the full gate against a real PostgreSQL service
and builds the production images on every push and pull request.

## Server deployment (Docker + HTTPS)

1. Point a DNS A record for your domain at the server; open ports 80 and 443.
2. `python backend/scripts/init_docker_env.py --domain vault.example.com`
3. `docker compose -f compose.prod.yaml --env-file .env.prod up -d --build --wait`

Caddy obtains a TLS certificate automatically and serves the UI at `/`, the API at `/api`.
API docs are disabled in production. Back up `.env.prod` together with the database volume:
losing `VAULT_ENCRYPTION_KEY` makes stored secrets unreadable.

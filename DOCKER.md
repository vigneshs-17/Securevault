# Local Docker setup

Status: build and runtime verification passed on 2026-09-10 with Docker Engine
29.7.2 and Docker Compose 5.5.1 using WSL 2. API and PostgreSQL are healthy; the
migration service completed successfully.

## Prerequisites

Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
with its WSL 2 backend. Complete any required Windows restart and Docker Desktop
first-run setup. Use Linux containers. Verify `docker version` shows a server and
`docker compose version` succeeds before proceeding.

## Start

From PowerShell in `D:\secure vault`, with the backend environment activated:

```powershell
python backend/scripts/init_docker_env.py
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d --wait
docker compose --env-file .env.docker ps -a
```

The generator refuses to overwrite existing keys. It leaves `backend/.env`
unchanged. Generated passwords use URL-safe characters for the connection URL.
If supplying your own database password, URL-encode it appropriately rather than
placing arbitrary reserved characters in the Compose URL.

The database first initializes a non-superuser `securevault` owner for its own
database. Alembic runs as a one-shot migration service after database readiness.
The API starts only after migrations succeed. The application does not receive
the PostgreSQL administrator password.

Open [API documentation](http://127.0.0.1:8000/docs).

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
docker compose --env-file .env.docker exec api python -m alembic current
docker compose --env-file .env.docker exec api python -m alembic check
```

Expected: root message `SecureVault API is running`, revision
`0002_vault_metadata`, and no new migration operations detected. Register a
disposable account in the documentation UI and verify vault create/read/update/
delete, refresh and logout. Stop and start containers and confirm records persist.
These runtime checks passed, including encrypted item persistence after
`docker compose down` followed by `up -d --wait`, audit-chain verification,
refresh rotation/reuse rejection, and logout revocation. Alembic reports the
metadata revision at head with no schema drift; container dependencies pass
`pip check`. The disposable smoke-test account and its audit records remain in
the separate Docker database; its vault item was deleted after verification.

If port 8000 is occupied, set `SECUREVAULT_HTTP_PORT=8001` in `.env.docker`, then
use that port in browser and health requests. Do not regenerate encryption keys.

## Stop and retain data

```powershell
docker compose --env-file .env.docker down
```

The named `securevault-local_postgres_data` volume retains records. Do not add
`--volumes` / `-v` unless you intentionally want to delete the Docker database.
Back up the volume/database and `.env.docker` securely together. Resetting keys
while retaining ciphertext makes stored secrets unreadable. Changing environment
passwords does not automatically change users in an already initialized database.

## Isolation and limitations

- This stack starts a new Docker database, separate from the existing Windows
  PostgreSQL database. It does not adopt or copy your main vault database.
- PostgreSQL has no published host port. The API binds only to host loopback.
- The API runs as a non-root user with a read-only filesystem and dropped
  capabilities. `/tmp` is writable temporary storage.
- Only allowlisted backend source and migration files enter the build context;
  `.env`, virtual environments, tests and caches are excluded.
- `.env.docker` is local and ignored by Git. Docker administrators can inspect
  container environment variables. This is a local-development configuration,
  not a production secret-management or HTTPS solution.
- Rate limiting remains in-process, using one API worker. CORS allows the planned
  local frontend. Production proxy configuration is a later step.
- Python 3.12 and PostgreSQL 18 image tags receive upstream updates; rebuild and
  retest updates. Production image digest pinning and vulnerability checks remain
  part of deployment hardening.

Startup ordering follows the [Compose dependency documentation](https://docs.docker.com/compose/how-tos/startup-order/).
The volume path follows the [PostgreSQL 18 image layout](https://docs.docker.com/guides/postgresql/).

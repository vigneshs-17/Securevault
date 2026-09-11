# 🔐 SecureVault

![SecureVault application preview](docs/images/securevault-preview.png)

SecureVault is a full-stack, security-focused secrets and credential manager built with a responsive browser interface, **FastAPI**, **SQLAlchemy**, **PostgreSQL**, and modern cryptographic controls.

The project demonstrates how sensitive information such as passwords, API keys, tokens, and other secrets can be stored and managed securely while applying authentication, authorization, encryption, session management, audit logging, and API security controls.

SecureVault was designed as a cybersecurity and full-stack engineering project rather than a basic CRUD password manager.

---

## 🎯 Project Goals

SecureVault demonstrates practical implementation of:

- Secure authentication
- Password hashing
- JWT-based authorization
- Access and refresh token management
- Session revocation
- Encryption at rest
- User-level data isolation
- Secure vault CRUD operations
- Tamper-evident audit logging
- API rate limiting
- Security headers
- Environment-based secret management
- Automated security testing

---

## 🛡️ Security Architecture

SecureVault follows a layered security model:

```text
Client (Browser UI / API Client)
  │
  ▼
FastAPI Application Layer
  │
  ├── Security Headers (HSTS, CSP, nosniff, DENY, no-referrer)
  ├── Trusted Host Validation
  ├── Restricted CORS Policy
  ├── Rate Limiting (5 req/min on login)
  │
  ▼
Authentication Layer
  │
  ├── Argon2id Password Hashing
  ├── JWT Access Tokens (HS256, 15m expiration)
  ├── Refresh Tokens (UUID jti, 7d expiration)
  ├── Token Validation & Token Versioning
  └── Refresh Session Revocation & Concurrency Locking
  │
  ▼
Authorization Layer
  │
  └── User Ownership Enforcement (Strict IDOR / BOLA Prevention)
  │
  ▼
Service Layer
  │
  ├── User Service
  ├── Vault Service
  ├── Vault Crypto Service (Fernet AES-128-CBC + HMAC-SHA256)
  ├── Refresh Session Service
  └── Audit Service (HMAC-SHA256 Hash Chaining + Advisory Locks)
  │
  ▼
Database Layer (PostgreSQL / Alembic)
  │
  ├── Users
  ├── Encrypted Vault Items
  ├── Refresh Sessions
  └── Tamper-Evident Audit Logs
```

---

## 🔑 Authentication & Session Security

SecureVault implements token-based authentication using JWT combined with database-backed session state:

- **User Registration:** Validates email format and enforces strong password complexity (minimum 12 characters, uppercase, lowercase, digit, and special symbol).
- **Password Hashing:** Uses Argon2id via `pwdlib` to provide modern memory-hard and compute-hard password derivation.
- **Short-Lived Access Tokens:** Expire in 15 minutes by default, limiting the exposure window of any intercepted credential.
- **Stateful Refresh Sessions:** Long-lived tokens carry a unique UUID `jti` mapped to the `refresh_sessions` table in the database.
- **Token Rotation:** Using a refresh token revokes the previous session record and issues a new refresh token pair, preventing reuse.
- **Session Revocation:**
  - *Single Logout (`/auth/logout`):* Revokes the specific refresh session.
  - *Global Logout (`/auth/logout-all`):* Revokes all user refresh sessions and increments `token_version`.
  - *Password Change (`/auth/change-password`):* Invalids all active sessions and increments `token_version`.
- **Concurrency Protection:** Account-modifying endpoints acquire a `FOR NO KEY UPDATE` lock on the user row and re-verify `token_version` after acquiring the lock, defeating race conditions between concurrent requests.

---

## 🔒 Vault Encryption

Sensitive vault information is encrypted before being stored in the database.

```text
Plaintext Secret (Password / Note)
      │
      ▼
Encryption Layer (Fernet AES-128-CBC + HMAC-SHA256)
      │
      ▼
Encrypted Ciphertext
      │
      ▼
Database (vault_items.encrypted_password / encrypted_notes)
```

When an authorized user requests the secret:

```text
Database Ciphertext
      │
      ▼
Ownership & Authorization Check (user_id == current_user.id)
      │
      ▼
Decryption Layer
      │
      ▼
Plaintext Secret (Returned only to authenticated owner)
```

- **Algorithm:** Uses Python's `cryptography.fernet.Fernet` symmetric encryption.
- **Scope:** Passwords and notes are stored as ciphertext. Vault item list responses (`GET /vault/items`) omit secret fields entirely; decryption occurs only when an item is individually retrieved (`GET /vault/items/{item_id}`).
- **Key Separation:** The encryption key is loaded from the environment (`VAULT_ENCRYPTION_KEY`) and is never hardcoded or committed to source control.

---

## 👤 Authorization & User Isolation

Vault records are strictly isolated by their owning user.

- Every database query for vault items explicitly filters by both `VaultItem.id == item_id` and `VaultItem.user_id == user_id`.
- If an unowned record is requested, the application returns `404 Not Found` (preventing IDOR and existence leakage) and records an `ACCESS_DENIED_*` audit entry.
- Audit logs queried via `/audit/logs` are strictly filtered by the authenticated user's ID.

This protects against:
- **Insecure Direct Object Reference (IDOR)**
- **Broken Object Level Authorization (BOLA)**

---

## 📦 Vault Operations

Authenticated users can perform full CRUD operations on their vault records:

- **Create:** Adds a password or secure note; sensitive values are encrypted prior to persistence.
- **List:** Retrieves summary records (titles, usernames, websites, item types, and timestamps) without decrypting secret data.
- **Retrieve:** Fetches a single item, verifies ownership, decrypts secrets, and logs the read event.
- **Update:** Selectively updates fields; if a new password or note is provided, it is re-encrypted.
- **Delete:** Deletes the record and logs the deletion event.

---

## 📜 Audit Logging & Chain Integrity

Security-relevant operations (logins, failed attempts, item creation, reads, updates, deletions, password changes, and logouts) are recorded through an audit subsystem with tamper-evident integrity protection.

- **HMAC Chaining:** Each log entry calculates an HMAC-SHA256 signature using `AUDIT_INTEGRITY_KEY` over:
  `user_id | action | resource_type | resource_id | previous_hash`
- **Advisory Locking:** On PostgreSQL, `create_audit_log` uses a transaction-scoped advisory lock (`pg_advisory_xact_lock`) to serialize chain appends and prevent concurrent forks.
- **Verification Endpoint:** `GET /audit/verify` allows authenticated users to verify the continuity and cryptographic integrity of the global chain using constant-time comparison (`hmac.compare_digest`).

---

## 🚦 Rate Limiting

- **Login Protection:** `POST /auth/login` is rate-limited to **5 requests per minute per IP address** using `slowapi`.
- **Abuse Prevention:** Protects against automated credential stuffing, brute-force dictionary attacks, and denial-of-service attempts.
- **Architecture Note:** The default limiter uses in-memory storage local to each worker process; multi-worker deployments require shared storage (such as Redis) and a trusted reverse-proxy configuration.

---

## 🌐 API Security

The API layer incorporates multiple defensive perimeter controls:

- **Security Response Headers:** Configured via custom middleware:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - `Cache-Control: no-store, no-cache, must-revalidate, private`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production mode)
  - `Content-Security-Policy: default-src 'none'` (restricted API policy)
- **Host Validation:** `TrustedHostMiddleware` enforces `allowed_hosts`. In production, wildcard hosts and `testserver` are rejected at startup.
- **CORS Policy:** `CORSMiddleware` limits origins to explicit entries in `cors_origins`. Wildcard origins are rejected in production.
- **Validation:** Pydantic models validate data types, string lengths, and HTTP URL formats on all incoming request payloads.

---

## ⚙️ Configuration Security

Sensitive configuration parameters are loaded via environment variables using Pydantic `BaseSettings`:

```text
DATABASE_URL
JWT_SECRET_KEY
VAULT_ENCRYPTION_KEY
AUDIT_INTEGRITY_KEY
ALLOWED_HOSTS
CORS_ORIGINS
```

- **Strict Validation:** Keys must satisfy minimum entropy requirements (32+ characters for JWT and audit keys, valid Fernet key for vault encryption).
- **Production Guardrails:** If `ENVIRONMENT=production`, default or placeholder credentials cause an immediate startup failure.
- **Template Hygiene:** Safe templates (`backend/.env.example` and `.env.docker.example`) contain only placeholders. Real `.env` and `.env.docker` files are ignored by Git.

---

## 🧰 Technology Stack

### Backend
- **Python 3.12+**
- **FastAPI** — High-performance asynchronous API framework
- **Pydantic v2** — Request validation and configuration management
- **SQLAlchemy 2.0** — ORM and database abstraction

### Database & Migrations
- **PostgreSQL 18** — Production relational database with advisory locks
- **Alembic** — Versioned database schema migrations with guarded baseline adoption

### Frontend
- **HTML5 & CSS3** — Responsive custom dark interface with depth effects and reduced-motion support
- **Vanilla Modern JavaScript** — Zero external runtime framework dependencies
- **Node.js 22+** — Local loopback static asset server with strict allowlisting and CSP

### Security & Cryptography
- **Argon2id** (`pwdlib`) — Memory-hard password hashing
- **PyJWT** — Access and refresh token generation and verification
- **Fernet** (`cryptography`) — AES-128-CBC authenticated encryption for vault secrets
- **HMAC-SHA256** — Tamper-evident audit trail chaining
- **SlowAPI** — Endpoint rate limiting
- **Starlette Middleware** — Trusted hosts, CORS, and security headers

### Testing & Quality Assurance
- **Pytest** — Automated unit, integration, and security regression testing
- **FastAPI TestClient** — End-to-end API route testing
- **Ruff** — High-speed Python linter and formatter
- **Mypy** — Strict static type checking

### Development & Containerization
- **Docker & Docker Compose** — Hardened multi-container local stack
- **Git** — Version control with strict secret-exclusion policies

---

## 📁 Project Structure

```text
SecureVault/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── audit.py                # Audit log listing and verification endpoints
│   │   │   ├── auth.py                 # Registration, login, refresh, logout, password change
│   │   │   └── vault.py                # Authenticated vault CRUD endpoints
│   │   │
│   │   ├── core/
│   │   │   ├── auth.py                 # JWT extraction, user dependencies, locking
│   │   │   ├── config.py               # Pydantic BaseSettings & production validators
│   │   │   ├── security.py             # Argon2id hashing and JWT token creation
│   │   │   └── security_headers.py     # HTTP security headers & CSP middleware
│   │   │
│   │   ├── db/
│   │   │   ├── base.py                 # SQLAlchemy DeclarativeBase
│   │   │   ├── database.py             # Database engine & sessionmaker
│   │   │   ├── dependencies.py         # Session dependency provider
│   │   │   ├── init_db.py              # Database initialization entrypoint
│   │   │   └── migrate.py              # Guarded migration & baseline adoption logic
│   │   │
│   │   ├── models/
│   │   │   ├── audit_log.py            # Audit log SQLAlchemy model
│   │   │   ├── refresh_session.py      # Refresh session tracking model
│   │   │   ├── user.py                 # User account & token_version model
│   │   │   └── vault_item.py           # Encrypted vault item model
│   │   │
│   │   ├── schemas/
│   │   │   ├── audit_log.py            # Audit log Pydantic response schemas
│   │   │   ├── user.py                 # User & token Pydantic schemas
│   │   │   └── vault_item.py           # Vault item CRUD & projection schemas
│   │   │
│   │   ├── services/
│   │   │   ├── audit_integrity.py      # HMAC-SHA256 hash generation & verification
│   │   │   ├── audit_service.py        # Audit creation with advisory lock & chain verification
│   │   │   ├── refresh_session_service.py # Session creation, rotation, and revocation
│   │   │   ├── user_service.py         # Registration, complexity validation, password change
│   │   │   ├── vault_crypto.py         # Fernet encryption and decryption helpers
│   │   │   └── vault_service.py        # Vault business logic & user ownership checks
│   │   │
│   │   └── main.py                     # FastAPI application setup & router registration
│   │
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py  # Frozen baseline migration
│   │   │   └── 0002_vault_metadata.py  # Metadata, typed notes & timestamp migration
│   │   ├── env.py                      # Alembic execution environment
│   │   └── script.py.mako
│   │
│   ├── tests/
│   │   ├── conftest.py                 # Pytest fixtures & isolated database setup
│   │   ├── test_audit.py               # Audit log & hash chain integrity tests
│   │   ├── test_auth.py                # Authentication, token & revocation tests
│   │   ├── test_concurrency.py         # PostgreSQL concurrency & race condition tests
│   │   ├── test_encryption.py          # Fernet cryptographic operation tests
│   │   ├── test_failure_handling.py    # Error handling & transaction rollback tests
│   │   ├── test_frontend_metadata.py   # Frontend compatibility & metadata tests
│   │   ├── test_migrations.py          # Alembic migration & guarded adoption tests
│   │   ├── test_regressions.py         # Security regression tests
│   │   ├── test_security_headers.py    # Security response headers & CSP tests
│   │   └── test_vault.py               # Vault item CRUD & authorization tests
│   │
│   ├── scripts/
│   │   └── init_docker_env.py          # Secure environment generator for Docker
│   │
│   ├── .dockerignore
│   ├── .env.example                    # Backend environment template
│   ├── .gitignore
│   ├── alembic.ini                     # Migration configuration
│   ├── Dockerfile                      # Hardened non-root container definition
│   ├── requirements.txt                # Runtime dependencies
│   ├── requirements-dev.txt            # Development & testing dependencies
│   └── test_postgres.py                # PostgreSQL test runner helper
│
├── frontend/
│   ├── assets/
│   │   ├── Inter-LICENSE.txt           # Inter font license
│   │   ├── InterVariable.woff2         # Self-hosted variable font
│   │   └── Lucide-LICENSE.txt          # Lucide icons license
│   ├── tests/
│   │   ├── api.test.mjs                # Client API & token rotation unit tests
│   │   └── security.test.mjs           # Client password generator & health tests
│   ├── api.js                          # In-memory token management & API client
│   ├── app.js                          # Client state management & DOM controller
│   ├── icons.js                        # Inline SVG icon generator
│   ├── index.html                      # Semantic single-page shell
│   ├── landing.js                      # Unauthenticated marketing & sign-in views
│   ├── package.json
│   ├── README.md                       # Frontend documentation & security boundaries
│   ├── security.js                     # Password generator & composition assessment
│   ├── server.mjs                      # Hardened loopback static HTTP server
│   ├── style.css                       # Dark theme CSS with custom depth styling
│   ├── ui.js                           # UI primitives & HTML entity escaping
│   └── views.js                        # Vault, dashboard, settings, & activity views
│
├── docker/
│   └── init-db.sh                      # PostgreSQL unprivileged role initialization
│
├── docs/
│   └── images/
│       └── securevault-preview.png     # Application preview screenshot
│
├── .env.docker.example                 # Docker Compose environment template
├── .gitignore                          # Root Git ignore rules
├── compose.yaml                        # Multi-service local Compose stack
├── DOCKER.md                           # Docker setup and operational runbook
├── LICENSE                             # MIT License
└── README.md                           # Project documentation
```

---

## 🚀 Running SecureVault Locally

### 1. Clone the repository

```bash
git clone https://github.com/vigneshs-17/Securevault.git
cd Securevault
```

### 2. Enter the backend directory

```bash
cd backend
```

*Requirements:* Python 3.12 or newer and a running PostgreSQL instance (or use the Docker setup below).

### 3. Create a virtual environment

```powershell
python -m venv venv
```

### 4. Activate the environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 5. Install dependencies

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 6. Configure environment variables

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Generate secure random secrets:

```powershell
# Generate 48-byte URL-safe secrets for JWT and Audit integrity:
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Generate a 32-byte URL-safe base64 Fernet key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Update your `backend/.env` with your PostgreSQL database URL and the generated keys:

```text
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/securevault
JWT_SECRET_KEY=<your_generated_jwt_key>
VAULT_ENCRYPTION_KEY=<your_generated_fernet_key>
AUDIT_INTEGRITY_KEY=<your_generated_audit_key>
```

> [!WARNING]
> Keep a secure backup of your `VAULT_ENCRYPTION_KEY`. Changing or losing this key renders existing vault ciphertext permanently unreadable.

### 7. Initialize Database Migrations

For a new empty database, apply all migrations:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

For databases created before Alembic was introduced, adopt the baseline schema safely:

```powershell
python -m app.db.migrate adopt-existing
python -m alembic upgrade head
```

The guarded adoption tool compares table schemas, column types, nullability, defaults, indexes, and constraints against the frozen baseline before stamping, refusing already tracked or mismatched schemas.

### 8. Start the API

```powershell
uvicorn app.main:app --reload
```

The API will be available at:
```text
http://127.0.0.1:8000
```
Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

---

## 🧪 Running Tests

All testing commands should be run from the `backend/` directory with the virtual environment activated:

```powershell
python -m pytest -q
```

### Test Suite Results

- **Standard Pytest Suite (SQLite):**
  - **74 passed, 5 skipped** in ~19s.
  - The 5 skipped tests are PostgreSQL-only concurrency tests.
  - Tests create disposable temporary SQLite instances and generate isolated cryptographic keys for each run without touching your `.env` database.
- **Dedicated PostgreSQL Concurrency Suite:**
  - Run via the dedicated runner:
    ```powershell
    python test_postgres.py tests/test_concurrency.py
    ```
  - Coordinates real concurrent requests with separate database sessions, validating row locking, one-time refresh rotation, simultaneous password changes, and immediate access-token revocation upon account modification.
  - When run against PostgreSQL (`securevault_test`), all **79 tests pass**.

### Static Code Quality Checks

Run Ruff and Mypy from the `backend/` directory:

```powershell
python -m ruff check app tests
python -m mypy app
```

- **Ruff:** Clean pass (`All checks passed!`).
- **Mypy:** Clean pass (`Success: no issues found in 34 source files`).

### Frontend Unit Tests

Run client-side unit tests from the repository root (requires Node.js 22+):

```bash
node --test frontend/tests/*.test.mjs
```

- **9 unit tests pass**, validating API client request handling, in-memory token rotation, password generation entropy, and composition scoring.

---

## 🐳 Docker Development Setup

SecureVault includes an isolated multi-container local development stack. See [DOCKER.md](DOCKER.md) for full operational instructions.

### Starting the Stack

From PowerShell in the repository root:

```powershell
python backend/scripts/init_docker_env.py
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d --wait
docker compose --env-file .env.docker ps -a
```

### Docker Security Features

- **Non-Root API Execution:** Runs as UID `10001:10001` (`securevault`).
- **Read-Only Root Filesystem:** Root container filesystem is mounted read-only with a temporary `tmpfs` at `/tmp`.
- **Capability Dropping:** All Linux kernel capabilities are dropped (`cap_drop: [ALL]`).
- **Privilege Escalation Prevention:** `no-new-privileges: true` is enforced.
- **Isolated Database Network:** PostgreSQL publishes no host ports; only the internal Docker network can communicate with it.
- **Loopback Host Binding:** The API container binds strictly to loopback (`127.0.0.1:8000`).
- **Unprivileged Database Role:** Database tables are owned by a dedicated `securevault` role; the API never has access to the PostgreSQL superuser password.

### Stopping the Stack

```powershell
docker compose --env-file .env.docker down
```

Data persists in the named Docker volume `securevault-local_postgres_data`.

---

## 💻 Frontend Interface

SecureVault features a zero-dependency, security-focused web client located in `frontend/`. See [frontend/README.md](frontend/README.md) for details.

### Starting the Frontend

1. Ensure the API is running (locally or via Docker).
2. Start the loopback static server:
   ```bash
   node frontend/server.mjs
   ```
3. Open `http://127.0.0.1:3000` in your browser.
4. *VS Code Shortcut:* Press `Ctrl+Shift+B` to launch the automated `SecureVault: Start` build task.

### Frontend Security Controls

- **No Browser Storage for Tokens:** Access and refresh tokens are kept strictly in a private JavaScript closure in tab memory. They are **never** written to `localStorage`, `sessionStorage`, or cookies.
- **Automatic Session Purge:** Closing or refreshing the browser tab destroys token references immediately.
- **Inactivity Locking:** Automatic idle timeout locks the workspace and calls `/auth/logout`.
- **XSS Prevention:** All user-controlled values pass through an HTML entity escaping routine encoding `&`, `<`, `>`, `"`, and `'`.
- **Masking & Hiding:** Revealed passwords automatically re-mask after 30 seconds or whenever the browser window loses focus.
- **Local Static Server:** Binds strictly to `127.0.0.1:3000`, serves only an explicit allowlist of files, and enforces strict CSP.

---

## 🔐 Security Principles Demonstrated

SecureVault applies defense-in-depth principles across every architectural layer:

- **Defense in Depth:** Security is not entrusted to a single layer. Authentication, authorization, encryption, HTTP security headers, rate limiting, and database constraints operate synergistically.
- **Least Privilege:** Authenticated users can only view and manipulate their own records. Database containers run with unprivileged user roles. API containers execute with dropped capabilities.
- **Secure Storage:** Sensitive vault payloads are encrypted before disk writes occur. Plaintext passwords never enter database logs or persistence layers.
- **Secret Separation:** Cryptographic keys and database credentials are separated from source code via environment variables.
- **Explicit Session Control:** Stateless JWTs are paired with stateful refresh session records and user `token_version` tracking, enabling instant account-wide revocation.
- **Auditability:** Security events generate verifiable, HMAC-chained records resistant to retroactive manipulation.
- **Secure-by-Default API Design:** Strict CSP, anti-framing, strict MIME sniffing protection, host verification, and input constraints reduce exposed attack surface.

---

## ⚠️ Threats Addressed

| Threat | Mitigation |
|---|---|
| **Database Compromise (Data at Rest)** | AES-128-CBC authenticated encryption (Fernet) for passwords and notes |
| **Password Database Breach** | Argon2id memory-hard password hashing |
| **Unauthorized Vault Access / IDOR / BOLA** | User-level ownership validation on every CRUD query; 404 on unowned records |
| **Stolen Long-Lived Credentials** | Short-lived access tokens (15 minutes) |
| **Refresh Token Abuse / Token Replay** | Refresh token rotation and instant session revocation |
| **Session Persistence After Password Change** | Immediate revocation of all refresh sessions and increment of `token_version` |
| **Brute-Force & Credential Stuffing** | IP-scoped rate limiting on `/auth/login` |
| **Audit Log Tampering** | Tamper-evident HMAC-SHA256 hash chaining with transaction-scoped advisory locks |
| **Accidental Secret Disclosure in Git** | Strict `.gitignore` and template-only `.env.example` tracking |
| **Host Header Injection** | `TrustedHostMiddleware` with explicit host allowlists |
| **Cross-Origin API Abuse** | Strict `CORSMiddleware` without credentials or wildcard origins |
| **Clickjacking & MIME Sniffing** | `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` headers |

---

## 🧪 Security Testing

SecureVault includes comprehensive automated regression tests:
- **Authentication:** Validates password complexity, failed login rate limits, and token versioning.
- **Session Revocation:** Tests that single logout revokes the specific session and that password change or logout-all immediately terminates access across all clients.
- **Concurrency & Races:** Five dedicated PostgreSQL concurrency tests verify that simultaneous requests cannot reuse rotated refresh tokens or act on stale credentials.
- **Authorization Boundaries:** Tests verify that cross-user IDOR access attempts return 404 and record audit denial events.
- **Integrity Validation:** Verifies that modifying an audit entry breaks the cryptographic hash chain and is caught by `/audit/verify`.

---

## 🔍 Known Security Boundaries

- **Metadata Visibility:** Passwords and secure notes are encrypted at rest. Vault titles, usernames, websites, item types, and timestamps are stored in plaintext metadata to enable indexing, filtering, and sorting.
- **Shared Audit Chain:** `/audit/logs` returns records scoped to the requesting user. `/audit/verify` validates the global chain, exposing the total log count and any failing record ID to authenticated users.
- **HMAC Scope:** Audit HMACs cover `user_id`, `action`, `resource_type`, `resource_id`, and `previous_hash`. Timestamps and primary keys are not part of the HMAC preimage. Without an external cryptographic timestamping checkpoint, complete truncation of the chain tail cannot be detected by the database alone.
- **Rate Limiter Storage:** Rate limiting currently uses in-memory storage local to the running process. Multi-worker deployments require Redis-backed shared storage.
- **Zero-Knowledge Distinction:** SecureVault is a server-side encrypted vault manager. It is not an end-to-end zero-knowledge system; the server holds the decryption key during runtime operations.

---

## 🗺️ Planned Improvements

Future production and engineering enhancements include:

- **CI/CD Security Pipeline:** GitHub Actions automation for tests, linting, and type verification.
- **Automated Dependency Scanning:** Dependabot and container vulnerability scanners (Trivy).
- **Static Application Security Testing (SAST):** Integration of Semgrep and Bandit security scanners.
- **Production PostgreSQL Hardening:** Read replicas, connection pooling (PgBouncer), and automated snapshot backups.
- **Distributed Rate Limiting:** Redis-backed rate limiter storage for multi-worker deployments.
- **Structured JSON Logging:** Observability logging with correlation IDs and OpenTelemetry tracing.
- **Expanded Adversarial Tests:** Fuzzing and automated penetration test fixtures.
- **Production TLS Reverse Proxy:** Automated HTTPS configuration via Caddy or Nginx with Let's Encrypt.

---

## 🎓 What This Project Demonstrates

SecureVault demonstrates end-to-end competencies in:

- **Cybersecurity Engineering:** Cryptographic controls, session invalidation architecture, threat mitigation, and tamper-evident audit logging.
- **Backend Engineering:** High-performance RESTful API design with FastAPI, SQLAlchemy 2.0 ORM modeling, transaction integrity, and database migrations.
- **Frontend Development:** Vanilla modern JavaScript, custom CSS depth design, accessible UI patterns, and secure in-memory credential handling.
- **DevSecOps & Operations:** Container privilege minimization, non-root execution, reproducible environments, and automated test-driven verification.

---

## 📄 License

SecureVault is open-source software released under the [MIT License](LICENSE).

Third-party asset licenses:
- Inter font: [frontend/assets/Inter-LICENSE.txt](frontend/assets/Inter-LICENSE.txt)
- Lucide icons: [frontend/assets/Lucide-LICENSE.txt](frontend/assets/Lucide-LICENSE.txt)

---

## ⚠️ Disclaimer

SecureVault is an educational and portfolio cybersecurity project.

While it demonstrates secure software engineering practices and cryptographic controls, it has not undergone an independent third-party professional security audit and should not be used as a production enterprise credential manager without additional review, operational hardening, and penetration testing.

---

## 👨‍💻 Author

**Vignesh S**  
*B.Tech Cybersecurity Student*

- **Focus Areas:** Application Security, Cloud Security, Backend Engineering, DevSecOps, Security Automation

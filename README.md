# 🔐 SecureVault

SecureVault is a security-focused secrets and credential management backend built with **FastAPI**, **SQLAlchemy**, and modern cryptographic controls.

The project demonstrates how sensitive information such as passwords, API keys, tokens, and other secrets can be stored and managed securely while applying authentication, authorization, encryption, session management, audit logging, and API security controls.

SecureVault was designed as a cybersecurity-focused backend engineering project rather than a basic CRUD password manager.

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

SecureVault follows a layered security model.

```text
Client
  │
  ▼
FastAPI Application
  │
  ├── Security Headers
  ├── Trusted Host Validation
  ├── CORS Policy
  ├── Rate Limiting
  │
  ▼
Authentication Layer
  │
  ├── Password Hashing
  ├── JWT Access Tokens
  ├── Refresh Tokens
  ├── Token Validation
  └── Session Revocation
  │
  ▼
Authorization Layer
  │
  └── User Ownership Enforcement
  │
  ▼
Service Layer
  │
  ├── User Service
  ├── Vault Service
  ├── Encryption Service
  ├── Refresh Session Service
  └── Audit Service
  │
  ▼
Database Layer
  │
  ├── Users
  ├── Encrypted Vault Items
  ├── Refresh Sessions
  └── Audit Logs
```

---

## 🔑 Authentication & Session Security

SecureVault implements token-based authentication using JWT.

The authentication system supports:

- User registration
- Secure password hashing
- User login
- Short-lived access tokens
- Refresh tokens
- Refresh-session tracking
- Token revocation
- Password-change session invalidation

This prevents authentication from depending entirely on long-lived stateless tokens.

---

## 🔒 Vault Encryption

Sensitive vault information is encrypted before being stored in the database.

```text
Plaintext Secret
      │
      ▼
Encryption Layer
      │
      ▼
Encrypted Ciphertext
      │
      ▼
Database
```

When an authorized user requests the secret:

```text
Database Ciphertext
      │
      ▼
Authorization Check
      │
      ▼
Decryption Layer
      │
      ▼
Plaintext Secret
```

The encryption key is supplied through environment configuration and is **never intended to be committed to source control**.

---

## 👤 Authorization & User Isolation

Vault records are associated with their owning user.

Operations enforce ownership checks so authenticated users cannot access another user's vault records.

This protects against common authorization vulnerabilities such as:

**IDOR — Insecure Direct Object Reference**

and

**Broken Object Level Authorization (BOLA).**

---

## 📦 Vault Operations

Authenticated users can perform CRUD operations on their vault records.

Supported operations include:

- Create vault item
- Retrieve vault items
- Update vault item
- Delete vault item

Sensitive values remain encrypted while stored.

---

## 📜 Audit Logging

Security-relevant activity is recorded through the audit subsystem.

Audit events can provide visibility into actions involving authentication and protected resources.

SecureVault also includes integrity protection for audit records, helping demonstrate tamper-evident security logging rather than ordinary application logging alone.

---

## 🚦 Rate Limiting

Login is limited to 5 requests per minute per client IP. Other endpoints currently
have no rate limits. The default limiter storage is in memory and is local to each
process; a multi-worker deployment needs shared storage and trusted proxy configuration.

This helps protect authentication and application functionality against:

- Brute-force attempts
- Credential attacks
- Automated abuse
- Excessive API requests

---

## 🌐 API Security

The application includes additional HTTP/API security controls such as:

- CORS configuration
- Trusted host validation
- Security response headers
- Environment-aware configuration

These controls provide additional defense around the API boundary.

---

## ⚙️ Configuration Security

Sensitive configuration is loaded from environment variables.

Examples include:

```text
DATABASE_URL
JWT_SECRET_KEY
VAULT_ENCRYPTION_KEY
AUDIT_INTEGRITY_KEY
```

The real `.env` file is excluded from Git.

A safe template is provided:

```text
backend/.env.example
```

Developers should create their own `.env` file and provide secure values locally.

---

## 🧰 Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy

### Security

- JWT authentication
- Password hashing
- Fernet-based encryption
- Refresh-session management
- Audit integrity protection
- Rate limiting
- Security headers
- CORS and trusted-host controls

### Testing

- Pytest
- FastAPI TestClient

### Development

- Git
- Python virtual environments
- Environment-based configuration

---

## 📁 Project Structure

```text
SecureVault/
│
├── backend/
│   │
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── vault.py
│   │   │   └── audit.py
│   │   │
│   │   ├── core/
│   │   │   ├── auth.py
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── security_headers.py
│   │   │
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── database.py
│   │   │   ├── dependencies.py
│   │   │   └── init_db.py
│   │   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── vault_item.py
│   │   │   ├── refresh_session.py
│   │   │   └── audit_log.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── user.py
│   │   │   ├── vault_item.py
│   │   │   └── audit_log.py
│   │   │
│   │   ├── services/
│   │   │   ├── user_service.py
│   │   │   ├── vault_service.py
│   │   │   ├── vault_crypto.py
│   │   │   ├── refresh_session_service.py
│   │   │   ├── audit_service.py
│   │   │   └── audit_integrity.py
│   │   │
│   │   └── main.py
│   │
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_vault.py
│   │   ├── test_encryption.py
│   │   ├── test_audit.py
│   │   └── test_security_headers.py
│   │
│   ├── .env.example
│   ├── .gitignore
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Running SecureVault Locally

### 1. Clone the repository

```bash
git clone <repository-url>
cd SecureVault
```

### 2. Enter the backend

```bash
cd backend
```

Use Python 3.12 or newer and a running PostgreSQL server.

### 3. Create a virtual environment

Windows:

```powershell
python -m venv venv
```

### 4. Activate the environment

PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 5. Install dependencies

```powershell
pip install -r requirements.txt
```

### 6. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Then replace the placeholder values with secure local secrets. Use the installed
Psycopg 3 driver in the URL:

```text
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/securevault
```

Create the database and database user in PostgreSQL first. URL-encode special
characters in the username/password. Generate separate JWT and audit keys by
running the first command twice, and a Fernet key with the second:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep the generated values in your local `.env`. Keep a secure backup of the vault
key: changing or losing it makes existing vault ciphertext unreadable.

Initialize tables for a new database:

```powershell
python -m app.db.init_db
```

This creates missing tables; it does not migrate existing table schemas.

### 7. Start the API

```powershell
uvicorn app.main:app --reload
```

The development API will normally be available at:

```text
http://127.0.0.1:8000
```

---

## 🧪 Running Tests

From the `backend` directory:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests create a temporary SQLite database and generate disposable cryptographic
keys before the application loads. Each test gets fresh tables and seeded test
users; your `.env` database is not used. SQLite tests do not validate PostgreSQL
locking or production deployment behavior.

Static checks from `backend`:

```powershell
python -m ruff check app tests
python -m mypy app
```

The test suite covers important functionality including authentication, encryption, vault operations, audit functionality, and HTTP security controls.

---

## 🔐 Security Principles Demonstrated

SecureVault applies several important application-security principles:

### Defense in Depth

Security is enforced across authentication, authorization, encryption, API controls, logging, and configuration rather than relying on one mechanism.

### Least Privilege

Authenticated users are restricted to resources they are authorized to access.

### Secure Storage

Sensitive vault data is encrypted before persistence.

### Secret Separation

Application secrets and cryptographic keys are kept outside source code through environment configuration.

### Session Control

Refresh sessions can be tracked and invalidated instead of relying solely on long-lived stateless authentication.

### Auditability

Security-relevant operations can be recorded with integrity protection.

### Secure-by-Default API Design

Security headers, host validation, CORS restrictions, validation, and rate limiting reduce the exposed attack surface.

---

## ⚠️ Threats Addressed

The project is designed to demonstrate mitigations for threats including:

| Threat | Mitigation |
|---|---|
| Database disclosure | Encryption at rest |
| Password database compromise | Password hashing |
| Unauthorized vault access | Authentication + ownership validation |
| IDOR / BOLA | User-level authorization |
| Stolen long-lived credentials | Short-lived access tokens |
| Refresh-token abuse | Refresh-session management |
| Session persistence after password change | Session invalidation |
| Brute-force/API abuse | Rate limiting |
| Audit-log manipulation | Integrity protection |
| Secret leakage through Git | `.env` exclusion |
| Host-header abuse | Trusted host validation |
| Unsafe cross-origin access | Restricted CORS policy |

---

## 🧪 Security Testing

SecureVault includes automated tests covering security-critical functionality.

Testing is used to verify behavior rather than assuming security controls work correctly.

Run the commands above for the current result; the suite also includes regression tests for validation, token expiry, configuration, and import order.

---

## Known Security Boundaries

- Passwords and notes are encrypted; titles, usernames, and websites are plaintext.
- `/audit/logs` is user-scoped. `/audit/verify` checks the global chain and exposes
  global counts and a failing record ID to authenticated users.
- Audit HMACs cover the action, user, resource, and previous hash, but not timestamps
  or row IDs. Legacy unhashed rows are supported before the chain starts. Without an
  externally trusted checkpoint, removing the entire chain or its tail cannot always
  be detected. PostgreSQL audit appends use a transaction-scoped advisory lock;
  the SQLite test suite does not establish multi-process concurrency guarantees.
- Refresh-session lookup locks the row in PostgreSQL to serialize use of the same
  token. Authentication and vault writes commit together with their audit entry;
  a failure before that commit rolls the operation back. Cross-request races with
  password changes or logout-all still need PostgreSQL concurrency testing and hardening.
- Single-session logout revokes the refresh token; its access token remains usable
  until expiry. Logout-all and password changes also revoke existing access tokens.

## 🗺️ Planned Improvements

Future engineering improvements may include:

- Dockerized deployment
- CI/CD security pipeline
- Dependency vulnerability scanning
- Static application security testing
- Database migrations
- PostgreSQL production configuration
- Structured application logging
- Expanded adversarial security tests
- Threat-model documentation
- Production deployment hardening

---

## 🎓 What This Project Demonstrates

SecureVault combines concepts from:

**Cybersecurity Engineering**

- Cryptography
- Authentication
- Authorization
- Secure session management
- API security
- Auditability
- Threat mitigation

**Backend Engineering**

- REST API development
- Database modeling
- Service-layer architecture
- Configuration management
- Validation
- Automated testing

**Software Engineering**

- Modular architecture
- Separation of concerns
- Version control
- Reproducible environments
- Test-driven verification

---

## ⚠️ Disclaimer

SecureVault is an educational and portfolio cybersecurity project.

It demonstrates secure engineering techniques but has not undergone an independent professional security audit and should not be treated as a production credential-management system without additional review, hardening, deployment controls, and security testing.

---

## 👨‍💻 Author

**Vignesh S**

B.Tech Cybersecurity Student

Interests:

- Cybersecurity Engineering
- Application Security
- Backend Engineering
- Cloud Security
- Security Automation
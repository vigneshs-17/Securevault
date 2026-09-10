# SecureVault frontend

A responsive dark interface with original CSS depth effects, self-hosted Inter,
Lucide icons, accessible dialogs and reduced-motion support. No runtime package dependencies.

## Run locally

Start the Docker backend using DOCKER.md. With Node 22 or later, run
`node frontend/server.mjs` from the project root, then visit http://127.0.0.1:3000.
Run `node --test frontend/tests/*.test.mjs` for client tests.
The server binds to loopback and serves only an explicit asset allowlist.

## Features

- Registration, sign-in, dashboard and session locking.
- Password and secure-note creation, search, sorting, viewing, editing and deletion.
- Password reveal with automatic hiding; clipboard copying with feedback.
- Cryptographically random password generation with length and character controls.
- On-demand weak/reused password checks, server audit integrity verification,
  account activity and active refresh sessions.
- Account password changes, sign-out across sessions, inactivity timeout and motion preferences.

## Security boundaries

Tokens and entry content stay in tab memory; reloading requires sign-in. Locking
clears client data and revokes the refresh session. Single-session logout access
tokens expire independently; logout-all invalidates them through the backend.
Passwords hide after 30 seconds or window blur. Clipboard contents are not erased.

Password health is a local composition/reuse estimate, not breach detection.
An explicit scan reads passwords from the API and keeps only results in memory.
Copy/scan activity labelled "This tab" is temporary; server audit records persist.
Audit integrity checks the shared server chain. Session device/location data is
not collected. Legacy entries have no invented creation timestamps.

Passwords and note contents use server-side encryption at rest. Titles, usernames,
websites, item types and timestamps are metadata and are not encrypted. This is
not a zero-knowledge vault. The local API is http://127.0.0.1:8000; production HTTPS,
deployment configuration and operational hardening remain separate work.

Inter and Lucide license notices are included in assets/.

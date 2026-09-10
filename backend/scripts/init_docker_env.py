"""Generate local Docker credentials without overwriting existing keys."""
import base64
import secrets
from pathlib import Path


def main():
    destination = Path(__file__).resolve().parents[2] / ".env.docker"
    values = {
        "POSTGRES_ADMIN_PASSWORD": secrets.token_urlsafe(48),
        "SECUREVAULT_DB_PASSWORD": secrets.token_urlsafe(48),
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "VAULT_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "AUDIT_INTEGRITY_KEY": secrets.token_urlsafe(48),
        "SECUREVAULT_HTTP_PORT": "8000",
    }
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as output:
            output.write("# Local Docker secrets. Do not commit or share this file.\n")
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    except FileExistsError:
        raise SystemExit(".env.docker already exists; preserved existing credentials and encryption keys.") from None
    print("Created .env.docker. Keep a secure backup alongside the database backup.")


if __name__ == "__main__":
    main()

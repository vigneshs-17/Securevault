"""Run tests in an isolated schema of the local securevault_test database."""
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main():
    backend = Path(__file__).resolve().parent
    configured = os.environ.get("SECUREVAULT_TEST_DATABASE_URL")
    if not configured:
        values = dotenv_values(backend / ".env")
        if not values.get("DATABASE_URL"):
            raise SystemExit("Set DATABASE_URL in the local .env or SECUREVAULT_TEST_DATABASE_URL.")
        try:
            url = make_url(values["DATABASE_URL"])
        except Exception:
            raise SystemExit("Invalid database URL in .env.") from None
        if url.get_backend_name() != "postgresql":
            raise SystemExit("The local .env must use PostgreSQL for this helper.")
        configured = url.set(drivername="postgresql+psycopg", database="securevault_test").render_as_string(hide_password=False)
    env = os.environ.copy()
    env["SECUREVAULT_TEST_DATABASE_URL"] = configured
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], cwd=backend, env=env)


if __name__ == "__main__":
    raise SystemExit(main())

import os
import secrets
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Override every setting before importing the application, including when a real
# .env exists. Never connect the tests to a developer's database.
_test_directory = TemporaryDirectory(prefix="securevault-tests-")
_database_url = "sqlite:///" + (Path(_test_directory.name) / "test.db").as_posix()
_schema_engine = None
_schema_name = None
if os.environ.get("SECUREVAULT_TEST_DATABASE_URL"):
    try:
        test_url = make_url(os.environ["SECUREVAULT_TEST_DATABASE_URL"])
        if (test_url.drivername != "postgresql+psycopg"
                or test_url.database != "securevault_test"
                or test_url.host not in {"localhost", "127.0.0.1", "::1"}
                or test_url.query):
            raise ValueError("Unsafe test database target")
    except Exception:
        raise pytest.UsageError(
            "Use a local postgresql+psycopg URL for securevault_test without query parameters."
        ) from None
    _schema_engine = create_engine(test_url, hide_parameters=True)
    _schema_name = "sv_test_" + secrets.token_hex(12)
    with _schema_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "securevault_test"
        connection.execute(text(f'CREATE SCHEMA "{_schema_name}"'))
    _database_url = test_url.update_query_dict(
        {"options": "-csearch_path=" + _schema_name}
    ).render_as_string(hide_password=False)

os.environ.update({
    "DATABASE_URL": _database_url,
    "ENVIRONMENT": "testing",
    "JWT_SECRET_KEY": secrets.token_urlsafe(48),
    "JWT_ALGORITHM": "HS256",
    "VAULT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "AUDIT_INTEGRITY_KEY": secrets.token_urlsafe(48),
    "ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
    "CORS_ORIGINS": "http://localhost:3000",
    "DOCS_ENABLED": "true",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
    "REFRESH_TOKEN_EXPIRE_DAYS": "7",
})

from app.api.auth import limiter as auth_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.database import engine  # noqa: E402
from app.db.migrate import upgrade_database  # noqa: E402


client = TestClient(app)

TEST_EMAIL = "test@securevault.com"
TEST_PASSWORD = "SecureVaultFinal456!"


@pytest.fixture(autouse=True)
def isolated_database():
    if _schema_name:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == _schema_name
    upgrade_database(engine)
    for email, password in (
        (TEST_EMAIL, TEST_PASSWORD),
        ("isolationuser@securevault.com", "IsolationUser123!"),
    ):
        response = client.post("/auth/register", json={"email": email, "password": password})
        assert response.status_code == 200
    auth_limiter.reset()
    yield
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    auth_limiter.reset()


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    if _schema_engine is not None:
        with _schema_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{_schema_name}" CASCADE'))
        _schema_engine.dispose()
    _test_directory.cleanup()


@pytest.fixture
def access_token() -> str:
    response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def pytest_configure(config):
    # Avoid shared Windows pytest temp directories owned by another account.
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(_test_directory.name) / "pytest")

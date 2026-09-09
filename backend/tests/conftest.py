import os
import secrets
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Override every setting before importing the application, including when a real
# .env exists. Never connect the tests to a developer's database.
_test_directory = TemporaryDirectory(prefix="securevault-tests-")
os.environ.update({
    "DATABASE_URL": "sqlite:///" + (Path(_test_directory.name) / "test.db").as_posix(),
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


client = TestClient(app)

TEST_EMAIL = "test@securevault.com"
TEST_PASSWORD = "SecureVaultFinal456!"


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(engine)
    for email, password in (
        (TEST_EMAIL, TEST_PASSWORD),
        ("isolationuser@securevault.com", "IsolationUser123!"),
    ):
        response = client.post("/auth/register", json={"email": email, "password": password})
        assert response.status_code == 200
    auth_limiter.reset()
    yield
    Base.metadata.drop_all(engine)
    auth_limiter.reset()


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
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

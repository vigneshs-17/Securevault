import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.api.auth import limiter as auth_limiter
from app.main import app


client = TestClient(app)

TEST_EMAIL = "test@securevault.com"
TEST_PASSWORD = "SecureVaultFinal456!"


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    auth_limiter.reset()
    yield


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
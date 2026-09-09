import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.auth import limiter
from app.core.config import Settings, settings
from app.db.database import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog

client = TestClient(app)


@pytest.mark.parametrize("field", ["title", "password"])
def test_null_required_vault_field_is_rejected(field, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    item = client.post("/vault/items", headers=headers, json={
        "title": "Keep title", "password": "Keep secret",
    }).json()
    response = client.patch(f"/vault/items/{item['id']}", headers=headers, json={field: None})
    assert response.status_code == 422
    saved = client.get(f"/vault/items/{item['id']}", headers=headers).json()
    assert saved["title"] == "Keep title"
    assert saved["password"] == "Keep secret"


def test_optional_vault_fields_can_be_cleared(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    item = client.post("/vault/items", headers=headers, json={
        "title": "Keep title", "password": "Keep secret", "notes": "Remove me",
        "username": "Remove me", "website": "https://example.com",
    }).json()
    cleared = {"notes": None, "username": None, "website": None}
    response = client.patch(f"/vault/items/{item['id']}", headers=headers, json=cleared)
    assert response.status_code == 200
    saved = client.get(f"/vault/items/{item['id']}", headers=headers).json()
    assert all(saved[field] is None for field in cleared)
    assert saved["password"] == "Keep secret"


def test_website_database_length_is_validated(access_token):
    response = client.post("/vault/items", headers={"Authorization": f"Bearer {access_token}"},
                           json={"title": "Test", "password": "secret",
                                 "website": "https://example.com/" + "a" * 500})
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint,token_type", [
    ("/auth/me", "access"), ("/auth/refresh", "refresh"), ("/auth/logout", "refresh"),
])
def test_missing_expiry_is_rejected(endpoint, token_type):
    token = jwt.encode({"sub": "1", "token_type": token_type, "token_version": 0,
                        "jti": "test-jti", "iat": datetime.now(timezone.utc)},
                       settings.jwt_secret_key, algorithm="HS256")
    response = (client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
                if endpoint == "/auth/me" else
                client.post(endpoint, json={"refresh_token": token}))
    assert response.status_code == 401


@pytest.mark.parametrize("endpoint", ["/auth/refresh", "/auth/logout"])
def test_malformed_refresh_subject_returns_401(endpoint):
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": None, "token_type": "refresh", "jti": "test-jti",
                        "iat": now, "exp": now + timedelta(minutes=5)},
                       settings.jwt_secret_key, algorithm="HS256")
    assert client.post(endpoint, json={"refresh_token": token}).status_code == 401


@pytest.mark.parametrize("key", ["x" * 44, "!" * 44, "short"])
def test_invalid_fernet_key_rejected_at_startup(key):
    with pytest.raises(ValidationError, match="valid Fernet key"):
        Settings(vault_encryption_key=key)


def test_limiter_is_shared_and_enforces_login_limit():
    assert app.state.limiter is limiter
    responses = [client.post("/auth/login", json={"email": "unknown@example.com",
                                                 "password": "WrongPassword123!"})
                 for _ in range(6)]
    assert [r.status_code for r in responses] == [401] * 5 + [429]
    assert responses[-1].headers["Cache-Control"].startswith("no-store")


def test_redoc_csp_allows_its_assets():
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "https://cdn.jsdelivr.net" in response.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" in response.headers["Content-Security-Policy"]


def test_missing_tail_hash_is_detected(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    client.post("/vault/items", headers=headers, json={"title": "Test", "password": "secret"})
    with SessionLocal() as db:
        log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        log.integrity_hash = None
        db.commit()
    assert client.get("/audit/verify", headers=headers).json()["valid"] is False


@pytest.mark.parametrize("module", ["app.models.user", "app.models.audit_log", "app.db.init_db"])
def test_model_imports_work_in_fresh_process(module):
    result = subprocess.run([sys.executable, "-c", f"import {module}"],
                            env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_database_initializer_creates_all_tables(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + (tmp_path / "init.db").as_posix()
    code = ("from app.db.init_db import init_db; init_db(); "
            "from app.db.database import engine; from sqlalchemy import inspect; "
            "assert set(inspect(engine).get_table_names()) == "
            "{'users', 'vault_items', 'refresh_sessions', 'audit_logs'}")
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

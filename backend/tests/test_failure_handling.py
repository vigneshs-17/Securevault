import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.db.base import Base
from app.db.database import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.schemas.user import UserCreate
from app.services.user_service import create_user

client = TestClient(app, raise_server_exceptions=False)


def database_snapshot():
    with SessionLocal() as db:
        return {table.name: list(db.execute(select(table).order_by(table.c.id)))
                for table in Base.metadata.sorted_tables}


@pytest.mark.parametrize("operation", [
    "login", "refresh", "logout", "logout-all", "change-password",
    "create", "update", "delete",
])
def test_audit_failure_rolls_back_entire_operation(operation, monkeypatch):
    credentials = {"email": "test@securevault.com", "password": "SecureVaultFinal456!"}
    tokens = client.post("/auth/login", json=credentials).json()
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    item = client.post("/vault/items", headers=headers,
                       json={"title": "Original", "password": "Original secret"}).json()
    before = database_snapshot()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit storage failure")

    monkeypatch.setattr("app.api.auth.create_audit_log", fail_audit)
    monkeypatch.setattr("app.services.vault_service.create_audit_log", fail_audit)
    if operation == "login":
        response = client.post("/auth/login", json=credentials)
    elif operation in {"refresh", "logout"}:
        response = client.post("/auth/" + operation, json={"refresh_token": tokens["refresh_token"]})
    elif operation == "logout-all":
        response = client.post("/auth/logout-all", headers=headers)
    elif operation == "change-password":
        response = client.post("/auth/change-password", headers=headers, json={
            "current_password": credentials["password"], "new_password": "ReplacementPassword123!",
        })
    elif operation == "create":
        response = client.post("/vault/items", headers=headers,
                               json={"title": "New", "password": "New secret"})
    elif operation == "update":
        response = client.patch(f"/vault/items/{item['id']}", headers=headers, json={"title": "Changed"})
    else:
        response = client.delete(f"/vault/items/{item['id']}", headers=headers)
    assert response.status_code == 500
    assert database_snapshot() == before


def test_registration_race_returns_conflict_and_recovers_session(monkeypatch):
    with SessionLocal() as db:
        scalar = db.scalar
        calls = 0

        def stale_first_read(*args, **kwargs):
            nonlocal calls
            calls += 1
            return None if calls == 1 else scalar(*args, **kwargs)

        monkeypatch.setattr(db, "scalar", stale_first_read)
        with pytest.raises(HTTPException) as error:
            create_user(db, UserCreate(email="test@securevault.com", password="SecureVaultFinal456!"))
        assert error.value.status_code == 409
        assert db.scalar(select(AuditLog).limit(1)) is None


@pytest.mark.parametrize("field", ["jwt_secret_key", "audit_integrity_key"])
@pytest.mark.parametrize("value", [
    "replace_with_a_strong_random_secret_at_least_32_chars", " " * 40, "secret" + " " * 40,
])
def test_production_rejects_known_placeholder_or_padding(field, value):
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(environment="production", allowed_hosts="vault.example.com", **{field: value})


@pytest.mark.parametrize("corruption", ["non_ascii", "all_hashes_missing"])
def test_corrupted_audit_hashes_fail_closed(corruption, access_token):
    headers = {"Authorization": "Bearer " + access_token}
    client.post("/vault/items", headers=headers, json={"title": "Test", "password": "secret"})
    with SessionLocal() as db:
        logs = db.query(AuditLog).order_by(AuditLog.id).all()
        if corruption == "non_ascii":
            logs[-1].integrity_hash = "\u00e9" * 64
        else:
            for log in logs:
                log.integrity_hash = None
        db.commit()
    response = client.get("/audit/verify", headers=headers)
    assert response.status_code == 200
    assert response.json()["valid"] is False

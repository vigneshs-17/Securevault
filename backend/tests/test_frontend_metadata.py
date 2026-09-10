from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.database import SessionLocal
from app.models.vault_item import VaultItem

client = TestClient(app)

def test_standalone_notes_are_encrypted_and_metadata_stays_safe(access_token):
    headers = {"Authorization": "Bearer " + access_token}
    created = client.post("/vault/items", headers=headers, json={"title": "Private note", "item_type": "note", "notes": "Synthetic private words"})
    assert created.status_code == 201
    item_id = created.json()["id"]
    listing = client.get("/vault/items", headers=headers).json()[0]
    assert listing["item_type"] == "note"
    assert listing["created_at"] and listing["updated_at"]
    assert "notes" not in listing and "password" not in listing
    with SessionLocal() as db:
        item = db.scalar(select(VaultItem).where(VaultItem.id == item_id))
        assert item.encrypted_notes != "Synthetic private words"
    detail = client.get(f"/vault/items/{item_id}", headers=headers).json()
    assert detail["notes"] == "Synthetic private words"
    assert client.patch(f"/vault/items/{item_id}", headers=headers, json={"notes": None}).status_code == 422
    assert client.patch(f"/vault/items/{item_id}", headers=headers, json={"notes": "Updated private words"}).status_code == 200
    changed = client.get(f"/vault/items/{item_id}", headers=headers).json()
    assert changed["updated_at"] >= detail["updated_at"]

def test_note_and_password_content_requirements(access_token):
    headers = {"Authorization": "Bearer " + access_token}
    assert client.post("/vault/items", headers=headers, json={"title": "Missing password"}).status_code == 422
    assert client.post("/vault/items", headers=headers, json={"title": "Empty note", "item_type": "note"}).status_code == 422
    assert client.post("/vault/items", headers=headers, json={"title": "Invalid type", "item_type": "other", "password": "abc"}).status_code == 422

def test_active_sessions_are_scoped_and_do_not_expose_tokens(access_token):
    headers = {"Authorization": "Bearer " + access_token}
    other = client.post("/auth/login", json={"email": "isolationuser@securevault.com", "password": "IsolationUser123!"}).json()
    sessions = client.get("/auth/sessions", headers=headers).json()
    other_sessions = client.get("/auth/sessions", headers={"Authorization": "Bearer " + other["access_token"]}).json()
    assert len(sessions) == 1
    assert set(sessions[0]) == {"id", "created_at", "expires_at"}
    assert sessions[0]["id"] != other_sessions[0]["id"]
    assert client.get("/auth/sessions").status_code == 401

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog


client = TestClient(app)


USER_B_EMAIL = "isolationuser@securevault.com"
USER_B_PASSWORD = "IsolationUser123!"


def test_audit_logs_require_authentication():
    response = client.get("/audit/logs")

    assert response.status_code in (401, 403)


def test_authenticated_user_can_view_audit_logs(access_token):
    response = client.get(
        "/audit/logs",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


def test_audit_chain_verification(access_token):
    response = client.get(
        "/audit/verify",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["valid"] is True
    assert data["message"] == "Audit chain integrity verified"
    assert data["total_logs"] >= 1
    assert data["verified_logs"] >= 1


def test_audit_tampering_is_detected(access_token):
    db: Session = SessionLocal()

    target_log = None
    original_action = None

    try:
        target_log = (
            db.query(AuditLog)
            .filter(AuditLog.integrity_hash.is_not(None))
            .order_by(AuditLog.id.desc())
            .first()
        )

        assert target_log is not None

        original_action = target_log.action

        target_log.action = "TAMPERED_TEST"
        db.commit()

        response = client.get(
            "/audit/verify",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["valid"] is False
        assert data["tampered_log_id"] == target_log.id
        assert data["reason"] == "Integrity hash does not match"

    finally:
        if target_log is not None and original_action is not None:
            target_log.action = original_action
            db.commit()

        db.close()


def test_users_can_only_view_their_own_audit_logs(access_token):
    headers_a = {
        "Authorization": f"Bearer {access_token}"
    }

    # Create an event belonging to User A.
    create_response = client.post(
        "/vault/items",
        headers=headers_a,
        json={
            "title": "Audit Isolation Test",
            "username": "audit-owner",
            "password": "AuditIsolation123!",
            "website": "https://audit-isolation.example.com",
            "notes": "This item belongs to User A",
        },
    )

    assert create_response.status_code == 201

    user_a_item_id = create_response.json()["id"]

    # Ensure User B exists.
    register_response = client.post(
        "/auth/register",
        json={
            "email": USER_B_EMAIL,
            "password": USER_B_PASSWORD,
        },
    )

    assert register_response.status_code in (200, 409)

    # Authenticate as User B.
    login_response = client.post(
        "/auth/login",
        json={
            "email": USER_B_EMAIL,
            "password": USER_B_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    user_b_access_token = login_response.json()["access_token"]

    headers_b = {
        "Authorization": f"Bearer {user_b_access_token}"
    }

    # Get User B's identity.
    me_response = client.get(
        "/auth/me",
        headers=headers_b,
    )

    assert me_response.status_code == 200

    user_b_id = me_response.json()["id"]

    # User B requests their audit logs.
    logs_response = client.get(
        "/audit/logs",
        headers=headers_b,
    )

    assert logs_response.status_code == 200

    logs = logs_response.json()

    assert isinstance(logs, list)

    # Every returned audit record must belong to User B.
    assert all(
        log["user_id"] == user_b_id
        for log in logs
    )

    # User A's vault CREATE audit entry must not leak into User B's logs.
    leaked_user_a_log = any(
        log["action"] == "CREATE"
        and log["resource_type"] == "VAULT_ITEM"
        and log["resource_id"] == user_a_item_id
        for log in logs
    )

    assert leaked_user_a_log is False
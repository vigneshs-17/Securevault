from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)

TEST_EMAIL = "test@securevault.com"
TEST_PASSWORD = "SecureVaultFinal456!"


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "SecureVault API is running"
    }


def test_login_with_wrong_password():
    response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_with_valid_credentials():
    response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_auth_me_without_token():
    response = client.get("/auth/me")

    assert response.status_code in (401, 403)


def test_auth_me_with_valid_token():
    login_response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == TEST_EMAIL


def test_refresh_token_rotation():
    login_response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": old_refresh_token
        },
    )

    assert refresh_response.status_code == 200

    new_refresh_token = refresh_response.json()["refresh_token"]

    assert new_refresh_token != old_refresh_token

    reuse_response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": old_refresh_token
        },
    )

    assert reuse_response.status_code == 401
    assert (
        reuse_response.json()["detail"]
        == "Invalid or revoked refresh token"
    )

def test_refresh_token_reuse_revokes_all_sessions_and_access_token():
    login_response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )
    assert login_response.status_code == 200
    initial_tokens = login_response.json()
    r1 = initial_tokens["refresh_token"]

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": r1},
    )
    assert refresh_response.status_code == 200
    rotated_tokens = refresh_response.json()
    r2 = rotated_tokens["refresh_token"]
    a2 = rotated_tokens["access_token"]

    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {a2}"})
    assert me_resp.status_code == 200

    replay_response = client.post(
        "/auth/refresh",
        json={"refresh_token": r1},
    )
    assert replay_response.status_code == 401
    assert replay_response.json()["detail"] == "Invalid or revoked refresh token"

    r2_response = client.post(
        "/auth/refresh",
        json={"refresh_token": r2},
    )
    assert r2_response.status_code == 401

    me_revoked_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {a2}"})
    assert me_revoked_resp.status_code == 401
    assert me_revoked_resp.json()["detail"] == "Authentication token has been revoked"



def test_invalid_access_token_is_rejected():
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer this.is.not.a.valid.jwt"
        },
    )

    assert response.status_code == 401


def test_expired_access_token_is_rejected(access_token):
    valid_payload = jwt.decode(
        access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "verify_exp": False,
        },
    )

    expired_payload = valid_payload.copy()

    expired_payload["exp"] = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {expired_token}"
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Invalid or expired authentication token"
    )


def test_refresh_token_cannot_be_used_as_access_token():
    login_response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    refresh_token = login_response.json()["refresh_token"]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {refresh_token}"
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token required"


def test_access_token_with_wrong_token_type_is_rejected(access_token):
    payload = jwt.decode(
        access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "verify_exp": False,
        },
    )

    payload["token_type"] = "something_else"

    invalid_token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {invalid_token}"
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token required"


def test_access_token_without_token_version_is_rejected(access_token):
    payload = jwt.decode(
        access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "verify_exp": False,
        },
    )

    payload.pop("token_version", None)

    invalid_token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {invalid_token}"
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Invalid or expired authentication token"
    )


def test_logout_all_revokes_existing_access_token():
    login_response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    logout_response = client.post(
        "/auth/logout-all",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert logout_response.status_code == 200
    assert (
        logout_response.json()["message"]
        == "Logged out from all devices successfully"
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication token has been revoked"
    )


def test_password_change_revokes_existing_access_token():
    email = f"password-change-{uuid4().hex}@securevault.com"

    old_password = "ChangePasswordOld123!"
    new_password = "ChangePasswordNew456!"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": old_password,
        },
    )

    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": old_password,
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    change_response = client.post(
        "/auth/change-password",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        json={
            "current_password": old_password,
            "new_password": new_password,
        },
    )

    assert change_response.status_code == 200
    assert (
        change_response.json()["message"]
        == "Password changed successfully"
    )

    old_token_response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert old_token_response.status_code == 401
    assert (
        old_token_response.json()["detail"]
        == "Authentication token has been revoked"
    )

    old_password_login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": old_password,
        },
    )

    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": new_password,
        },
    )

    assert new_password_login.status_code == 200

    new_access_token = new_password_login.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {new_access_token}"
        },
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == email

def test_login_failure_rate_limit_per_email():
    from app.api.auth import limiter as auth_limiter
    target_email = "rate_limit_target@securevault.com"
    client.post("/auth/register", json={"email": target_email, "password": "StrongPassword123!"})

    # 5 failed attempts return 401; reset IP limiter after each to ensure per-email limit is what triggers
    for _ in range(5):
        resp = client.post("/auth/login", json={"email": target_email, "password": "WrongPassword123!"})
        assert resp.status_code == 401
        auth_limiter.reset()

    # 6th attempt returns 429 via per-email failure limit
    limited_resp = client.post("/auth/login", json={"email": target_email, "password": "WrongPassword123!"})
    assert limited_resp.status_code == 429
    message = limited_resp.json().get("detail") or limited_resp.json().get("error")
    assert "Rate limit exceeded" in message


def test_unknown_account_failed_login_is_audit_logged():
    from app.db.database import SessionLocal
    from app.models.audit_log import AuditLog

    secret_attempt = "SecretNotStored123!"
    resp = client.post("/auth/login", json={"email": "ghost@securevault.com", "password": secret_attempt})
    assert resp.status_code == 401

    with SessionLocal() as db:
        latest_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert latest_log is not None
        assert latest_log.action == "LOGIN_FAILED"
        assert latest_log.resource_type == "AUTH"
        # Verify the submitted password was NOT stored
        for col in ("action", "resource_type", "previous_hash", "integrity_hash"):
            val = getattr(latest_log, col, "")
            assert secret_attempt not in str(val)


def test_password_minimum_length_schema_validation(access_token):
    # Registration with password < 12 characters is rejected at schema level (422)
    resp = client.post("/auth/register", json={"email": "short@example.com", "password": "short"})
    assert resp.status_code == 422

    # Password change with new_password < 12 characters is rejected at schema level (422)
    headers = {"Authorization": f"Bearer {access_token}"}
    change_resp = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": TEST_PASSWORD, "new_password": "short"},
    )
    assert change_resp.status_code == 422

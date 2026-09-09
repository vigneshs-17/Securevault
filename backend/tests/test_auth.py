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
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

USER_B_EMAIL = "isolationuser@securevault.com"
USER_B_PASSWORD = "IsolationUser123!"


def test_vault_requires_authentication():
    response = client.get("/vault/items")

    assert response.status_code in (401, 403)


def test_create_vault_item(access_token):
    response = client.post(
        "/vault/items",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        json={
            "title": "Pytest Account",
            "username": "pytest-user",
            "password": "PytestSecret123!",
            "website": "https://example.com",
            "notes": "Created by automated test",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert "id" in data
    assert data["title"] == "Pytest Account"
    assert data["message"] == "Vault item created successfully"


def test_list_vault_items(access_token):
    response = client.get(
        "/vault/items",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


def test_full_vault_crud_flow(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    create_response = client.post(
        "/vault/items",
        headers=headers,
        json={
            "title": "CRUD Test Account",
            "username": "crud-user",
            "password": "OriginalSecret123!",
            "website": "https://crud.example.com",
            "notes": "Original notes",
        },
    )

    assert create_response.status_code == 201

    item_id = create_response.json()["id"]

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    get_response = client.get(
        f"/vault/items/{item_id}",
        headers=headers,
    )

    assert get_response.status_code == 200

    get_data = get_response.json()

    assert get_data["id"] == item_id
    assert get_data["title"] == "CRUD Test Account"
    assert get_data["username"] == "crud-user"
    assert get_data["password"] == "OriginalSecret123!"

    # Pydantic HttpUrl normalizes the URL with a trailing slash.
    assert get_data["website"] == "https://crud.example.com/"

    assert get_data["notes"] == "Original notes"

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    update_response = client.patch(
        f"/vault/items/{item_id}",
        headers=headers,
        json={
            "title": "Updated CRUD Account",
            "password": "UpdatedSecret456!",
            "notes": "Updated notes",
        },
    )

    assert update_response.status_code == 200

    # ---------------------------------------------------------
    # VERIFY UPDATE
    # ---------------------------------------------------------

    updated_get_response = client.get(
        f"/vault/items/{item_id}",
        headers=headers,
    )

    assert updated_get_response.status_code == 200

    updated_data = updated_get_response.json()

    assert updated_data["title"] == "Updated CRUD Account"
    assert updated_data["password"] == "UpdatedSecret456!"
    assert updated_data["notes"] == "Updated notes"

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    delete_response = client.delete(
        f"/vault/items/{item_id}",
        headers=headers,
    )

    assert delete_response.status_code == 200

    # ---------------------------------------------------------
    # VERIFY DELETE
    # ---------------------------------------------------------

    deleted_get_response = client.get(
        f"/vault/items/{item_id}",
        headers=headers,
    )

    assert deleted_get_response.status_code == 404


def test_user_isolation_read(access_token):
    headers_a = {
        "Authorization": f"Bearer {access_token}"
    }

    create_response = client.post(
        "/vault/items",
        headers=headers_a,
        json={
            "title": "User A Secret",
            "username": "user-a",
            "password": "UserASecret123!",
            "website": "https://usera.example.com",
            "notes": "Owned by User A",
        },
    )

    assert create_response.status_code == 201

    item_id = create_response.json()["id"]

    register_response = client.post(
        "/auth/register",
        json={
            "email": USER_B_EMAIL,
            "password": USER_B_PASSWORD,
        },
    )

    assert register_response.status_code in (200, 409)

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

    response = client.get(
        f"/vault/items/{item_id}",
        headers=headers_b,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Vault item not found"


def test_user_isolation_update(access_token):
    headers_a = {
        "Authorization": f"Bearer {access_token}"
    }

    create_response = client.post(
        "/vault/items",
        headers=headers_a,
        json={
            "title": "Protected Account",
            "username": "owner-user",
            "password": "OwnerSecret123!",
            "website": "https://protected.example.com",
            "notes": "User A owns this item",
        },
    )

    assert create_response.status_code == 201

    item_id = create_response.json()["id"]

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

    update_response = client.patch(
        f"/vault/items/{item_id}",
        headers=headers_b,
        json={
            "title": "HACKED BY USER B",
            "password": "AttackerPassword123!",
        },
    )

    assert update_response.status_code == 404

    owner_get_response = client.get(
        f"/vault/items/{item_id}",
        headers=headers_a,
    )

    assert owner_get_response.status_code == 200

    data = owner_get_response.json()

    assert data["title"] == "Protected Account"
    assert data["password"] == "OwnerSecret123!"


def test_user_isolation_delete(access_token):
    headers_a = {
        "Authorization": f"Bearer {access_token}"
    }

    create_response = client.post(
        "/vault/items",
        headers=headers_a,
        json={
            "title": "Delete Protected Account",
            "username": "owner-delete-user",
            "password": "DeleteSecret123!",
            "website": "https://delete-protected.example.com",
            "notes": "User A owns this item",
        },
    )

    assert create_response.status_code == 201

    item_id = create_response.json()["id"]

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

    delete_response = client.delete(
        f"/vault/items/{item_id}",
        headers=headers_b,
    )

    assert delete_response.status_code == 404

    owner_get_response = client.get(
        f"/vault/items/{item_id}",
        headers=headers_a,
    )

    assert owner_get_response.status_code == 200

    data = owner_get_response.json()

    assert data["id"] == item_id
    assert data["title"] == "Delete Protected Account"
    assert data["password"] == "DeleteSecret123!"
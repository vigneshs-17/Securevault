from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.main import app
from app.models.vault_item import VaultItem
from app.services.vault_crypto import decrypt_value, encrypt_value


client = TestClient(app)


def test_vault_secrets_are_encrypted_at_rest(access_token):
    plaintext_password = "EncryptionTestSecret123!"
    plaintext_notes = "Sensitive encryption-at-rest test notes"

    response = client.post(
        "/vault/items",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        json={
            "title": "Encryption Test Account",
            "username": "encryption-user",
            "password": plaintext_password,
            "website": "https://encryption.example.com",
            "notes": plaintext_notes,
        },
    )

    assert response.status_code == 201

    item_id = response.json()["id"]

    db: Session = SessionLocal()

    try:
        vault_item = db.get(VaultItem, item_id)

        assert vault_item is not None

        # Password must never be stored as plaintext.
        assert vault_item.encrypted_password != plaintext_password
        assert plaintext_password not in vault_item.encrypted_password

        # Notes must also be encrypted when provided.
        assert vault_item.encrypted_notes is not None
        assert vault_item.encrypted_notes != plaintext_notes
        assert plaintext_notes not in vault_item.encrypted_notes

        # Verify the encrypted values can be correctly decrypted.
        assert (
            decrypt_value(vault_item.encrypted_password)
            == plaintext_password
        )

        assert (
            decrypt_value(vault_item.encrypted_notes)
            == plaintext_notes
        )

    finally:
        db.close()


def test_same_plaintext_produces_different_ciphertext():
    plaintext = "SameSecret123!"

    ciphertext_one = encrypt_value(plaintext)
    ciphertext_two = encrypt_value(plaintext)

    # Fernet encryption should not produce identical ciphertext
    # for repeated encryption of the same plaintext.
    assert ciphertext_one != ciphertext_two

    # Both ciphertext values must still decrypt correctly.
    assert decrypt_value(ciphertext_one) == plaintext
    assert decrypt_value(ciphertext_two) == plaintext
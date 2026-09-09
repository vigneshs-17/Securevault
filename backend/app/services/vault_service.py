from sqlalchemy.orm import Session

from app.models.vault_item import VaultItem
from app.schemas.vault_item import VaultItemCreate, VaultItemUpdate
from app.services.audit_service import create_audit_log
from app.services.vault_crypto import decrypt_value, encrypt_value


def create_vault_item(
    db: Session,
    user_id: int,
    item_data: VaultItemCreate,
) -> VaultItem:
    vault_item = VaultItem(
        user_id=user_id,
        title=item_data.title,
        username=item_data.username,
        encrypted_password=encrypt_value(item_data.password),
        website=(
            str(item_data.website)
            if item_data.website is not None
            else None
        ),
        encrypted_notes=(
            encrypt_value(item_data.notes)
            if item_data.notes
            else None
        ),
    )

    db.add(vault_item)
    db.flush()
    db.refresh(vault_item)

    create_audit_log(
        db=db,
        user_id=user_id,
        action="CREATE",
        resource_type="VAULT_ITEM",
        resource_id=vault_item.id,
    )

    return vault_item


def get_vault_items(
    db: Session,
    user_id: int,
):
    return (
        db.query(VaultItem)
        .filter(VaultItem.user_id == user_id)
        .order_by(VaultItem.id.desc())
        .all()
    )


def get_vault_item(
    db: Session,
    user_id: int,
    item_id: int,
):
    vault_item = (
        db.query(VaultItem)
        .filter(
            VaultItem.id == item_id,
            VaultItem.user_id == user_id,
        )
        .first()
    )

    if vault_item is None:
        create_audit_log(
            db=db,
            user_id=user_id,
            action="ACCESS_DENIED_READ",
            resource_type="VAULT_ITEM",
            resource_id=item_id,
        )
        return None

    create_audit_log(
        db=db,
        user_id=user_id,
        action="READ",
        resource_type="VAULT_ITEM",
        resource_id=vault_item.id,
    )

    return {
        "id": vault_item.id,
        "title": vault_item.title,
        "username": vault_item.username,
        "password": decrypt_value(vault_item.encrypted_password),
        "website": vault_item.website,
        "notes": (
            decrypt_value(vault_item.encrypted_notes)
            if vault_item.encrypted_notes
            else None
        ),
    }


def update_vault_item(
    db: Session,
    user_id: int,
    item_id: int,
    item_data: VaultItemUpdate,
) -> VaultItem | None:
    vault_item = (
        db.query(VaultItem)
        .filter(
            VaultItem.id == item_id,
            VaultItem.user_id == user_id,
        )
        .first()
    )

    if vault_item is None:
        create_audit_log(
            db=db,
            user_id=user_id,
            action="ACCESS_DENIED_UPDATE",
            resource_type="VAULT_ITEM",
            resource_id=item_id,
        )
        return None

    update_data = item_data.model_dump(exclude_unset=True)

    if "title" in update_data:
        vault_item.title = update_data["title"]

    if "username" in update_data:
        vault_item.username = update_data["username"]

    if "website" in update_data:
        website = update_data["website"]

        vault_item.website = (
            str(website)
            if website is not None
            else None
        )

    if "password" in update_data:
        vault_item.encrypted_password = encrypt_value(
            update_data["password"]
        )

    if "notes" in update_data:
        vault_item.encrypted_notes = (
            encrypt_value(update_data["notes"])
            if update_data["notes"] is not None
            else None
        )

    db.flush()
    db.refresh(vault_item)

    create_audit_log(
        db=db,
        user_id=user_id,
        action="UPDATE",
        resource_type="VAULT_ITEM",
        resource_id=vault_item.id,
    )

    return vault_item


def delete_vault_item(
    db: Session,
    user_id: int,
    item_id: int,
) -> bool:
    vault_item = (
        db.query(VaultItem)
        .filter(
            VaultItem.id == item_id,
            VaultItem.user_id == user_id,
        )
        .first()
    )

    if vault_item is None:
        create_audit_log(
            db=db,
            user_id=user_id,
            action="ACCESS_DENIED_DELETE",
            resource_type="VAULT_ITEM",
            resource_id=item_id,
        )
        return False

    resource_id = vault_item.id

    db.delete(vault_item)
    db.flush()

    create_audit_log(
        db=db,
        user_id=user_id,
        action="DELETE",
        resource_type="VAULT_ITEM",
        resource_id=resource_id,
    )

    return True
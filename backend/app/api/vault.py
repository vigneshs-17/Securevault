from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.vault_item import (
    VaultItemCreate,
    VaultItemListResponse,
    VaultItemResponse,
    VaultItemUpdate,
)
from app.services.vault_service import (
    create_vault_item,
    delete_vault_item,
    get_vault_item,
    get_vault_items,
    update_vault_item,
)


router = APIRouter(
    prefix="/vault",
    tags=["Vault"],
)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(
    item_data: VaultItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vault_item = create_vault_item(
        db=db,
        user_id=current_user.id,
        item_data=item_data,
    )

    return {
        "id": vault_item.id,
        "title": vault_item.title,
        "message": "Vault item created successfully",
    }


@router.get("/items", response_model=list[VaultItemListResponse])
def list_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_vault_items(
        db=db,
        user_id=current_user.id,
    )


@router.get("/items/{item_id}", response_model=VaultItemResponse)
def get_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vault_item = get_vault_item(
        db=db,
        user_id=current_user.id,
        item_id=item_id,
    )

    if vault_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault item not found",
        )

    return vault_item


@router.patch("/items/{item_id}")
def update_item(
    item_id: int,
    item_data: VaultItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vault_item = update_vault_item(
        db=db,
        user_id=current_user.id,
        item_id=item_id,
        item_data=item_data,
    )

    if vault_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault item not found",
        )

    return {
        "id": vault_item.id,
        "title": vault_item.title,
        "message": "Vault item updated successfully",
    }


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = delete_vault_item(
        db=db,
        user_id=current_user.id,
        item_id=item_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault item not found",
        )

    return {
        "message": "Vault item deleted successfully",
    }
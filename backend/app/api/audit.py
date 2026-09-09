from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_service import (
    get_user_audit_logs,
    verify_audit_chain,
)


router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
)


@router.get("/logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_audit_logs(
        db=db,
        user_id=current_user.id,
    )


@router.get("/verify")
def verify_integrity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return verify_audit_chain(db=db)
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.services.audit_integrity import (
    generate_audit_hash,
    verify_audit_hash,
)


def create_audit_log(
    db: Session,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
) -> AuditLog:
    # Serialize the global chain's append, including the empty-table case.
    # The transaction-scoped lock is released by the commit below.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7365637572657661)"))

    previous_log = (
        db.query(AuditLog)
        .filter(AuditLog.integrity_hash.is_not(None))
        .order_by(AuditLog.id.desc())
        .first()
    )

    previous_hash = (
        previous_log.integrity_hash
        if previous_log is not None
        else None
    )

    integrity_hash = generate_audit_hash(
        secret_key=settings.audit_integrity_key,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_hash=previous_hash,
    )

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_hash=previous_hash,
        integrity_hash=integrity_hash,
    )

    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return audit_log


def get_user_audit_logs(
    db: Session,
    user_id: int,
):
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.id.desc())
        .all()
    )


def verify_audit_chain(
    db: Session,
) -> dict:
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.id.asc())
        .all()
    )

    integrity_logs = [
        log
        for log in logs
        if log.integrity_hash is not None
    ]

    if not integrity_logs:
        return {
            "valid": True,
            "total_logs": len(logs),
            "verified_logs": 0,
            "legacy_logs": len(logs),
            "message": "No integrity-enabled audit logs found",
        }

    previous_hash = None

    for log in logs:
        if log.integrity_hash is None:
            if previous_hash is not None or log.previous_hash is not None:
                return {
                    "valid": False,
                    "tampered_log_id": log.id,
                    "reason": "Missing integrity hash in audit chain",
                }
            continue

        if log.previous_hash != previous_hash:
            return {
                "valid": False,
                "tampered_log_id": log.id,
                "reason": "Previous hash does not match",
            }

        is_valid = verify_audit_hash(
            secret_key=settings.audit_integrity_key,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            previous_hash=log.previous_hash,
            stored_hash=log.integrity_hash,
        )

        if not is_valid:
            return {
                "valid": False,
                "tampered_log_id": log.id,
                "reason": "Integrity hash does not match",
            }

        previous_hash = log.integrity_hash

    return {
        "valid": True,
        "total_logs": len(logs),
        "verified_logs": len(integrity_logs),
        "legacy_logs": len(logs) - len(integrity_logs),
        "message": "Audit chain integrity verified",
    }

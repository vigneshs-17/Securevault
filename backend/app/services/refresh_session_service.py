from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.refresh_session import RefreshSession


def create_refresh_session(
    db: Session,
    user_id: int,
    token_jti: str,
    expires_at: datetime,
) -> RefreshSession:
    session = RefreshSession(
        user_id=user_id,
        token_jti=token_jti,
        expires_at=expires_at,
    )

    db.add(session)
    db.flush()
    db.refresh(session)

    return session


def get_refresh_session(
    db: Session,
    token_jti: str,
) -> RefreshSession | None:
    return (
        db.query(RefreshSession)
        .filter(RefreshSession.token_jti == token_jti)
        .with_for_update()
        .first()
    )


def is_refresh_session_valid(
    session: RefreshSession,
) -> bool:
    if session.revoked_at is not None:
        return False

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at > datetime.now(timezone.utc)


def revoke_refresh_session(
    db: Session,
    session: RefreshSession,
) -> None:
    session.revoked_at = datetime.now(timezone.utc)

    db.flush()


def revoke_all_user_refresh_sessions(
    db: Session,
    user_id: int,
) -> int:
    sessions = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .all()
    )

    now = datetime.now(timezone.utc)

    for session in sessions:
        session.revoked_at = now

    db.flush()

    return len(sessions)


def cleanup_refresh_sessions(
    db: Session,
) -> int:
    sessions = db.query(RefreshSession).all()

    now = datetime.now(timezone.utc)
    deleted_count = 0

    for session in sessions:
        expires_at = session.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if session.revoked_at is not None or expires_at <= now:
            db.delete(session)
            deleted_count += 1

    db.commit()

    return deleted_count

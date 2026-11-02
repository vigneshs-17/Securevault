from collections import OrderedDict
from datetime import datetime, timezone
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import jwt
from jwt import InvalidTokenError

from app.core.auth import get_current_user, get_current_user_locked
from app.core.config import settings
from app.core.security import (
    create_access_token,
    DUMMY_HASH,
    create_refresh_token,
    verify_password,
)
from app.db.dependencies import get_db
from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.schemas.user import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.audit_service import create_audit_log
from app.services.refresh_session_service import (
    create_refresh_session,
    get_refresh_session,
    is_refresh_session_valid,
    revoke_all_user_refresh_sessions,
    revoke_refresh_session,
)
from app.services.user_service import (
    change_user_password,
    create_user,
    get_user_by_email,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

limiter = Limiter(key_func=get_remote_address)

# In-memory per-worker failure tracker.
# Note: Failure tracking is in-memory per worker process. In multi-worker deployments,
# a shared store (e.g., Redis) would be required for global synchronization.
_email_failures: OrderedDict[str, list[float]] = OrderedDict()
_email_failures_lock = threading.Lock()
MAX_EMAIL_LOGIN_FAILURES = 5
EMAIL_FAILURE_WINDOW_SECONDS = 60.0
MAX_EMAIL_FAILURE_ENTRIES = 10000
SYSTEM_USER_EMAIL = "system@securevault.internal"
SYSTEM_USER_PASSWORD_SENTINEL = "!"


def get_or_create_system_user(db: Session) -> User:
    system_user = db.query(User).filter(User.email == SYSTEM_USER_EMAIL).first()
    if system_user is None:
        system_user = User(
            email=SYSTEM_USER_EMAIL,
            hashed_password=SYSTEM_USER_PASSWORD_SENTINEL,
            token_version=0,
        )
        db.add(system_user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            system_user = db.query(User).filter(User.email == SYSTEM_USER_EMAIL).first()
    if system_user is None or system_user.hashed_password != SYSTEM_USER_PASSWORD_SENTINEL:
        raise RuntimeError("System user account is invalid or compromised")
    return system_user


def _prune_expired_failures_locked(now: float) -> None:
    expired_keys = []
    for k, timestamps in _email_failures.items():
        valid = [t for t in timestamps if now - t < EMAIL_FAILURE_WINDOW_SECONDS]
        if valid:
            _email_failures[k] = valid
        else:
            expired_keys.append(k)
    for k in expired_keys:
        _email_failures.pop(k, None)


def check_email_failure_limit(email: str) -> None:
    now = time.monotonic()
    key = email.strip().lower()
    with _email_failures_lock:
        timestamps = [t for t in _email_failures.get(key, []) if now - t < EMAIL_FAILURE_WINDOW_SECONDS]
        if timestamps:
            _email_failures[key] = timestamps
        else:
            _email_failures.pop(key, None)
        if len(timestamps) >= MAX_EMAIL_LOGIN_FAILURES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded: 5 per 1 minute",
            )


def record_email_login_failure(email: str) -> None:
    now = time.monotonic()
    key = email.strip().lower()
    with _email_failures_lock:
        _prune_expired_failures_locked(now)
        timestamps = [t for t in _email_failures.get(key, []) if now - t < EMAIL_FAILURE_WINDOW_SECONDS]
        timestamps.append(now)
        _email_failures[key] = timestamps
        _email_failures.move_to_end(key)
        while len(_email_failures) > MAX_EMAIL_FAILURE_ENTRIES:
            _email_failures.popitem(last=False)


def reset_email_login_failures(email: str) -> None:
    key = email.strip().lower()
    with _email_failures_lock:
        _email_failures.pop(key, None)


def reset_all_email_login_failures() -> None:
    with _email_failures_lock:
        _email_failures.clear()


@router.post("/register", response_model=UserResponse)
@limiter.limit("20/minute")
def register_user(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    return create_user(db, user_data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login_user(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    check_email_failure_limit(user_data.email)

    user = get_user_by_email(db, user_data.email, for_update=True)

    if user is None:
        record_email_login_failure(user_data.email)
        verify_password(user_data.password, DUMMY_HASH)
        system_user = get_or_create_system_user(db)
        create_audit_log(
            db=db,
            user_id=system_user.id,
            action="LOGIN_FAILED",
            resource_type="AUTH",
            resource_id=None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        user_data.password,
        user.hashed_password,
    ):
        record_email_login_failure(user_data.email)
        create_audit_log(
            db=db,
            user_id=user.id,
            action="LOGIN_FAILED",
            resource_type="AUTH",
            resource_id=user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    reset_email_login_failures(user_data.email)

    access_token = create_access_token(
        user_id=user.id,
        token_version=user.token_version,
    )

    refresh_token, token_jti, expires_at = create_refresh_token(
        user.id
    )

    create_refresh_session(
        db=db,
        user_id=user.id,
        token_jti=token_jti,
        expires_at=expires_at,
    )

    create_audit_log(
        db=db,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        resource_id=user.id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh_access_token(
    request: Request,
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "token_type", "jti"]},
        )

        user_id = int(payload["sub"])
        token_type = payload.get("token_type")
        token_jti = payload["jti"]

        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required",
            )

    except HTTPException:
        raise

    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, user_id, with_for_update={"key_share": True}, populate_existing=True)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    refresh_session = get_refresh_session(
        db=db,
        token_jti=token_jti,
    )

    if (
        refresh_session is not None
        and refresh_session.user_id == user.id
        and refresh_session.revoked_at is not None
    ):
        revoke_all_user_refresh_sessions(
            db=db,
            user_id=user.id,
        )
        user.token_version += 1
        db.flush()
        create_audit_log(
            db=db,
            user_id=user.id,
            action="REFRESH_TOKEN_REUSE_DETECTED",
            resource_type="AUTH",
            resource_id=user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    if (
        refresh_session is None
        or refresh_session.user_id != user.id
        or not is_refresh_session_valid(refresh_session)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    revoke_refresh_session(
        db=db,
        session=refresh_session,
    )

    new_access_token = create_access_token(
        user_id=user.id,
        token_version=user.token_version,
    )

    (
        new_refresh_token,
        new_token_jti,
        new_expires_at,
    ) = create_refresh_token(user.id)

    create_refresh_session(
        db=db,
        user_id=user.id,
        token_jti=new_token_jti,
        expires_at=new_expires_at,
    )

    create_audit_log(
        db=db,
        user_id=user.id,
        action="TOKEN_REFRESH",
        resource_type="AUTH",
        resource_id=user.id,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/logout")
def logout_user(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "token_type", "jti"]},
        )

        user_id = int(payload["sub"])
        token_type = payload.get("token_type")
        token_jti = payload["jti"]

        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required",
            )

    except HTTPException:
        raise

    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, user_id, with_for_update={"key_share": True}, populate_existing=True)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    refresh_session = get_refresh_session(
        db=db,
        token_jti=token_jti,
    )

    if (
        refresh_session is None
        or refresh_session.user_id != user_id
        or not is_refresh_session_valid(refresh_session)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    revoke_refresh_session(
        db=db,
        session=refresh_session,
    )

    create_audit_log(
        db=db,
        user_id=user_id,
        action="LOGOUT",
        resource_type="AUTH",
        resource_id=user_id,
    )

    return {
        "message": "Logged out successfully"
    }


@router.post("/logout-all")
def logout_all_devices(
    current_user: User = Depends(get_current_user_locked),
    db: Session = Depends(get_db),
):
    revoked_sessions = revoke_all_user_refresh_sessions(
        db=db,
        user_id=current_user.id,
    )

    current_user.token_version += 1
    db.flush()

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="LOGOUT_ALL",
        resource_type="AUTH",
        resource_id=current_user.id,
    )

    return {
        "message": "Logged out from all devices successfully",
        "revoked_sessions": revoked_sessions,
    }


@router.post("/change-password")
def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user_locked),
    db: Session = Depends(get_db),
):
    if not verify_password(
        password_data.current_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if verify_password(
        password_data.new_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    change_user_password(
        db=db,
        user=current_user,
        new_password=password_data.new_password,
    )

    revoked_sessions = revoke_all_user_refresh_sessions(
        db=db,
        user_id=current_user.id,
    )

    current_user.token_version += 1
    db.flush()

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="PASSWORD_CHANGED",
        resource_type="AUTH",
        resource_id=current_user.id,
    )

    return {
        "message": "Password changed successfully",
        "revoked_sessions": revoked_sessions,
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.get("/sessions")
def list_active_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.query(RefreshSession).filter(
        RefreshSession.user_id == current_user.id,
        RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > datetime.now(timezone.utc),
    ).order_by(RefreshSession.created_at.desc()).all()
    return [{"id": session.id, "created_at": session.created_at, "expires_at": session.expires_at}
            for session in sessions]

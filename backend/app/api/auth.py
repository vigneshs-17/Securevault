from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

import jwt
from jwt import InvalidTokenError

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.db.dependencies import get_db
from app.models.user import User
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


@router.post("/register", response_model=UserResponse)
def register_user(
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
    user = get_user_by_email(db, user_data.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        user_data.password,
        user.hashed_password,
    ):
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

    create_audit_log(
        db=db,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        resource_id=user.id,
    )

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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
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

    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, user_id)

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

    except (InvalidTokenError, KeyError, ValueError):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoked_sessions = revoke_all_user_refresh_sessions(
        db=db,
        user_id=current_user.id,
    )

    current_user.token_version += 1
    db.commit()

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
    current_user: User = Depends(get_current_user),
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
    db.commit()

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
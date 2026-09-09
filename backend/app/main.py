from fastapi import FastAPI
from fastapi import Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.audit import router as audit_router
from app.api.auth import limiter, router as auth_router
from app.api.vault import router as vault_router
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


app.state.limiter = limiter


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts_list,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


app.add_middleware(SecurityHeadersMiddleware)


app.include_router(auth_router)
app.include_router(vault_router)
app.include_router(audit_router)


@app.get("/")
def root():
    return {
        "message": "SecureVault API is running"
    }

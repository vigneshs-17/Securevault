from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.vault import router as vault_router
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware


limiter = Limiter(key_func=get_remote_address)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


app.state.limiter = limiter


app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


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
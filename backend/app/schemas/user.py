from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Bound input so hashing cannot be used for CPU exhaustion.
Password = Field(min_length=1, max_length=128)
AccountPassword = Field(min_length=12, max_length=128)
RESERVED_DOMAIN = "securevault.internal"
RESERVED_EMAIL_SUFFIX = f"@{RESERVED_DOMAIN}"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = AccountPassword

    @field_validator("email")
    @classmethod
    def validate_not_reserved(cls, v: EmailStr) -> EmailStr:
        normalized = str(v).strip().lower()
        if (
            normalized == f"system@{RESERVED_DOMAIN}"
            or normalized.endswith(RESERVED_EMAIL_SUFFIX)
            or normalized.endswith(f".{RESERVED_DOMAIN}")
        ):
            raise ValueError("value is not a valid email address")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Password


class UserResponse(BaseModel):
    id: int
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Password
    new_password: str = AccountPassword

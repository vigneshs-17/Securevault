from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Bound input so hashing cannot be used for CPU exhaustion.
Password = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Password


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
    new_password: str = Password
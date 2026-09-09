from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class VaultItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=1, max_length=4096)
    website: HttpUrl | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("title cannot be empty")

        return value

    @field_validator("username")
    @classmethod
    def validate_username(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("password cannot be empty")

        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class VaultItemUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    username: str | None = Field(
        default=None,
        max_length=255,
    )
    password: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
    )
    website: HttpUrl | None = Field(default=None, max_length=500)
    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator("title")
    @classmethod
    def validate_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            raise ValueError("title cannot be null")

        value = value.strip()

        if not value:
            raise ValueError("title cannot be empty")

        return value

    @field_validator("username")
    @classmethod
    def validate_username(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator("password")
    @classmethod
    def validate_password(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            raise ValueError("password cannot be null")

        if not value:
            raise ValueError("password cannot be empty")

        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class VaultItemResponse(BaseModel):
    id: int
    title: str
    username: str | None = None
    password: str
    website: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VaultItemListResponse(BaseModel):
    id: int
    title: str
    username: str | None = None
    website: str | None = None

    model_config = ConfigDict(from_attributes=True)
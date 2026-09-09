from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SecureVault"
    app_version: str = "1.0.0"
    environment: str = "development"

    database_url: str

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = Field(
        default=15,
        ge=1,
        le=120,
    )

    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
    )

    vault_encryption_key: str

    audit_integrity_key: str = Field(
        min_length=32,
    )

    allowed_hosts: str = (
        "127.0.0.1,"
        "localhost,"
        "testserver"
    )

    cors_origins: str = (
        "http://127.0.0.1:3000,"
        "http://localhost:3000"
    )

    docs_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        value = value.strip().lower()

        allowed = {
            "development",
            "testing",
            "production",
        }

        if value not in allowed:
            raise ValueError(
                "environment must be one of: "
                "development, testing, production"
            )

        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        value = value.strip().upper()

        if value != "HS256":
            raise ValueError(
                "jwt_algorithm must be HS256"
            )

        return value

    @field_validator("vault_encryption_key")
    @classmethod
    def validate_vault_encryption_key(
        cls,
        value: str,
    ) -> str:
        try:
            Fernet(value.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise ValueError("vault_encryption_key must be a valid Fernet key") from exc

        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment != "production":
            return self

        weak_values = {
            "changeme",
            "change-me",
            "secret",
            "password",
            "development",
            "test",
        }

        if self.jwt_secret_key.strip().lower() in weak_values:
            raise ValueError(
                "jwt_secret_key must not use a placeholder "
                "value in production"
            )

        if self.audit_integrity_key.strip().lower() in weak_values:
            raise ValueError(
                "audit_integrity_key must not use a placeholder "
                "value in production"
            )

        if "testserver" in self.allowed_hosts_list:
            raise ValueError(
                "testserver must not be allowed in production"
            )

        if "*" in self.allowed_hosts_list:
            raise ValueError(
                "wildcard allowed_hosts are not permitted "
                "in production"
            )

        if "*" in self.cors_origins_list:
            raise ValueError(
                "wildcard cors_origins are not permitted "
                "in production"
            )

        return self

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [
            host.strip()
            for host in self.allowed_hosts.split(",")
            if host.strip()
        ]

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
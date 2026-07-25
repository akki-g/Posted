from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "Posted"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./posted.db"
    frontend_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:19006",
        ]
    )
    dev_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    demo_mode: bool = True
    app_secret: SecretStr = SecretStr("dev-only-change-me")
    frontend_app_url: str = "http://127.0.0.1:8081/settings"

    schwab_client_id: str | None = None
    schwab_client_secret: str | None = None
    schwab_redirect_uri: str = "http://127.0.0.1:8000/api/v1/connections/schwab/callback"
    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_environment: str = "sandbox"
    plaid_webhook_url: str | None = None
    plaid_redirect_uri: str | None = None
    plaid_android_package_name: str = "com.posted.portfolio"
    openbb_fmp_api_key: str | None = None
    openbb_benzinga_api_key: str | None = None
    openbb_intrinio_api_key: str | None = None
    openbb_news_provider: str = "yfinance"
    sec_user_agent: str = "Posted contact@example.com"
    anthropic_api_key: str | None = None

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def schwab_configured(self) -> bool:
        return bool(self.schwab_client_id and self.schwab_client_secret)

    @property
    def plaid_configured(self) -> bool:
        return bool(self.plaid_client_id and self.plaid_secret)

    @property
    def ai_insights_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

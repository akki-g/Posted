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
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/google/callback"
    frontend_login_callback_url: str = "http://127.0.0.1:8081/login/callback"
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
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    finnhub_api_key: str | None = None
    market_data_yahoo_fallback: bool = True
    sec_user_agent: str = "Posted contact@example.com"
    anthropic_api_key: str | None = None
    # SignalWire SMS is deliberately opt-in. The local test number is mapped only
    # to DEV_USER_ID and is never a substitute for production account linking.
    # signalwire_space_url is the bare host, e.g. "example.signalwire.com".
    signalwire_space_url: str | None = None
    signalwire_project_id: str | None = None
    signalwire_api_token: SecretStr | None = None
    signalwire_from_number: str | None = None
    signalwire_local_test_phone: str | None = None
    # The exact public URL registered as the number's inbound webhook. SignalWire
    # signs the URL it POSTed to; behind a tunnel request.url is the internal
    # localhost URL, so signature checks need the public URL to reconstruct it.
    signalwire_webhook_url: str | None = None
    signalwire_allow_unsigned_webhooks: bool = False
    # Temporary: logs a safe (no secrets/PII) sweep of which signature header,
    # URL variant, algorithm, and encoding a rejected webhook's signature
    # would have matched, to pin down production signing mismatches. Turn
    # off once the verified scheme is confirmed - it's an extra HMAC sweep
    # per rejected request.
    signalwire_signature_diagnostics: bool = False

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
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def plaid_configured(self) -> bool:
        return bool(self.plaid_client_id and self.plaid_secret)

    @property
    def ai_insights_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)

    @property
    def finnhub_configured(self) -> bool:
        return bool(self.finnhub_api_key)

    @property
    def signalwire_configured(self) -> bool:
        return bool(
            self.signalwire_space_url
            and self.signalwire_project_id
            and self.signalwire_api_token
            and self.signalwire_from_number
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

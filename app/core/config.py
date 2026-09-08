from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # General
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "deckpilotAI"
    api_v1_prefix: str = Field(default="/api/v1", pattern=r"^/")

    # Security
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "deckpilotai-backend"
    jwt_audience: str = "deckpilotai"
    jwt_expire_minutes: int = Field(default=60 * 24, ge=5, le=60 * 24 * 30)
    key_encryption_secret: str = Field(min_length=32)

    # Database — Turso / libSQL
    turso_database_url: str = ""
    turso_auth_token: str = ""
    sqlite_database_url: str = "sqlite:///./deckpilotai_dev.db"

    # Cloudflare R2
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "deckpilotai"
    local_storage_dir: str = "./local_storage"

    # Frontend
    frontend_origin: str = (
        "http://localhost:3000,"
        "https://deckpilot-ai-frontend.aideckpilot.workers.dev,"
        "https://deckpilot-ai-frontend.creatorpilot-ai.workers.dev,"
        "https://deckpilot-ai-frontend.pages.dev"
    )
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    ai_provider_allowed_hosts: str = (
        "openrouter.ai,api.openai.com,generativelanguage.googleapis.com,"
        "api.groq.com,api.mistral.ai,api.anthropic.com,api.experientiallabs.ai,"
        "codecraftapi.com,api.codecraftapi.com"
    )

    # Request limits
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    db_echo: bool = False

    # Diagnostics & Observability
    slow_api_threshold_ms: int = Field(default=3000, ge=100)
    slow_agent_threshold_ms: int = Field(default=15000, ge=500)
    slow_llm_threshold_ms: int = Field(default=10000, ge=500)
    slow_render_threshold_ms: int = Field(default=15000, ge=500)
    log_retention_error_days: int = Field(default=90, ge=1)
    log_retention_warning_days: int = Field(default=14, ge=1)
    log_retention_resolved_days: int = Field(default=30, ge=1)

    # AI Providers & API Keys
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    llm_read_timeout_seconds: int = Field(default=120, ge=10, le=300)
    groq_api_key: str = ""
    mistral_api_key: str = ""
    experientiallabs_api_key: str = ""
    explabs_api_key: str = ""
    experientiallabs_base_url: str = "https://api.experientiallabs.ai/v1"
    codecraft_api_key: str = ""
    codecraft_base_url: str = "https://codecraftapi.com/v1"

    @property
    def effective_experientiallabs_api_key(self) -> str:
        return (self.experientiallabs_api_key or self.explabs_api_key or "").strip()

    @property
    def database_url(self) -> str:
        """Return Turso URL or fall back to local SQLite for development."""
        if self.turso_database_url:
            return self.turso_database_url
        return self.sqlite_database_url

    @property
    def environment(self) -> str:
        return self.app_env

    @property
    def is_secure_environment(self) -> bool:
        return self.app_env in {"staging", "production"}

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def ai_provider_allowed_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.ai_provider_allowed_hosts.split(",") if host.strip()]

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        insecure_markers = ("change-me", "development-secret", "example")
        for name, value in (
            ("JWT_SECRET", self.jwt_secret),
            ("KEY_ENCRYPTION_SECRET", self.key_encryption_secret),
        ):
            if any(marker in value.lower() for marker in insecure_markers):
                raise ValueError(f"{name} must be replaced with a secure random value")

        if not self.frontend_origins or "*" in self.frontend_origins:
            raise ValueError("FRONTEND_ORIGIN must contain explicit origins")

        if bool(self.turso_database_url) != bool(self.turso_auth_token):
            raise ValueError("TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be configured together")

        r2_values = (self.r2_endpoint_url, self.r2_access_key_id, self.r2_secret_access_key)
        if any(r2_values) and not all(r2_values):
            raise ValueError("All Cloudflare R2 connection values must be configured together")

        if self.app_env == "production":
            if not self.turso_database_url:
                raise ValueError("TURSO_DATABASE_URL is required in production")
            if not all(r2_values):
                raise ValueError("Cloudflare R2 storage is required in production")
            if any(not origin.startswith("https://") for origin in self.frontend_origins):
                raise ValueError("Production frontend origins must use HTTPS")
            if not self.allowed_host_list or "*" in self.allowed_host_list:
                raise ValueError("Production ALLOWED_HOSTS must be explicit")
            if self.db_echo:
                raise ValueError("DB_ECHO must be disabled in production")

        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

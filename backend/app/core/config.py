from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    placeholder_markers = (
        "replace-with",
        "replace_with",
        "change-me",
        "changeme",
        "placeholder",
        "your-",
        "your_",
    )
    return (
        not normalized
        or any(marker in normalized for marker in placeholder_markers)
        or "example.com" in normalized
        or normalized in {"secret", "changeme", "change-me", "password"}
    )


class Settings(BaseSettings):
    """環境変数から読み込むアプリケーション設定。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AUDIO_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "RyThM Music"
    environment: Literal["development", "test", "production"] = "development"
    app_secret: str = Field(
        default="development-only-change-me",
        validation_alias=AliasChoices("app_secret", "APP_SECRET", "AUDIO_APP_SECRET"),
        repr=False,
    )
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    database_url: str = Field(
        default="postgresql+psycopg://rythm_user:rythm_password@localhost:5432/rythm_music",
        repr=False,
    )
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)
    session_cookie_name: str = "rythm_session"
    csrf_cookie_name: str = "rythm_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_idle_hours: int = Field(default=24, ge=1, le=168)
    session_absolute_days: int = Field(default=14, ge=1, le=90)
    session_touch_interval_seconds: int = Field(default=300, ge=0, le=3600)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cors_origins: str = "http://localhost:5173"
    csrf_trusted_origins: str = "http://localhost:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    turnstile_secret_key: str = Field(default="", repr=False)
    turnstile_required: bool = False
    turnstile_expected_hostnames: str = ""
    email_verification_expire_hours: int = Field(default=24, ge=1, le=168)
    email_verification_resend_seconds: int = Field(default=300, ge=60, le=3600)
    password_reset_expire_minutes: int = Field(default=30, ge=10, le=120)
    terms_version: str = Field(default="2026-07-30", min_length=1, max_length=40)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_from_email: str = "noreply@example.com"
    smtp_use_tls: bool = True
    timezone: str = "Asia/Tokyo"
    upload_dir: Path = Path("storage/uploads")
    generated_dir: Path = Path("storage/generated")
    max_upload_bytes: int = 50 * 1024 * 1024
    max_audio_duration_sec: int = 600
    analysis_points_cost: int = 0
    generation_points_cost: int = 0
    registration_bonus: int = 0
    daily_login_bonus: int = 0
    auto_create_tables: bool = False
    rate_limit_requests: int = 60
    auth_rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    registration_rate_limit_per_hour: int = Field(default=5, ge=1, le=100)
    login_rate_limit_per_ten_minutes: int = Field(default=5, ge=1, le=100)
    verification_rate_limit_per_hour: int = Field(default=10, ge=1, le=100)
    email_action_rate_limit_per_hour: int = Field(default=3, ge=1, le=100)
    email_action_ip_rate_limit_per_hour: int = Field(default=10, ge=1, le=500)
    analysis_max_concurrency: int = Field(default=1, ge=1, le=4)
    analysis_queue_max_size: int = Field(default=8, ge=1, le=100)
    analysis_queue_wait_seconds: int = Field(default=900, ge=30, le=3600)
    genre_model_path: Path | None = None
    genre_model_metadata_path: Path | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_model: str = "gpt-4.1-mini"
    lyrics_api_url: str | None = None
    lyrics_api_key: str | None = Field(default=None, repr=False)
    lyrics_model: str = "whisper-1"
    music_provider: str = "demo"
    music_api_url: str | None = None
    music_status_url: str | None = None
    music_api_key: str | None = Field(default=None, repr=False)

    @field_validator("genre_model_path", "genre_model_metadata_path", mode="before")
    @classmethod
    def blank_path_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None requires Secure cookies")
        if self.environment != "production":
            return self

        errors: list[str] = []
        if len(self.app_secret) < 32 or _looks_like_placeholder(self.app_secret):
            errors.append("APP_SECRET must be a unique value of at least 32 characters")
        if not self.cookie_secure:
            errors.append("AUDIO_COOKIE_SECURE must be true")
        if not self.session_cookie_name.startswith("__Host-"):
            errors.append("AUDIO_SESSION_COOKIE_NAME must use the __Host- prefix")
        if not self.csrf_cookie_name.startswith("__Host-"):
            errors.append("AUDIO_CSRF_COOKIE_NAME must use the __Host- prefix")
        if self.analysis_max_concurrency != 1:
            errors.append("AUDIO_ANALYSIS_MAX_CONCURRENCY must be 1 on this deployment")
        if not self.frontend_url.startswith("https://"):
            errors.append("AUDIO_FRONTEND_URL must use https")
        frontend = urlparse(self.frontend_url)
        frontend_origin = f"{frontend.scheme}://{frontend.netloc}"
        frontend_hostname = (frontend.hostname or "").lower()
        if not self.turnstile_required:
            errors.append("AUDIO_TURNSTILE_REQUIRED must be true")
        if _looks_like_placeholder(self.turnstile_secret_key):
            errors.append("AUDIO_TURNSTILE_SECRET_KEY is required")
        if not self.expected_turnstile_hostnames:
            errors.append("AUDIO_TURNSTILE_EXPECTED_HOSTNAMES is required")
        elif frontend_hostname not in self.expected_turnstile_hostnames:
            errors.append("Turnstile hostnames must include the frontend hostname")
        if _looks_like_placeholder(self.smtp_host):
            errors.append("AUDIO_SMTP_HOST is required")
        if _looks_like_placeholder(self.smtp_username):
            errors.append("AUDIO_SMTP_USERNAME is required")
        if _looks_like_placeholder(self.smtp_password):
            errors.append("AUDIO_SMTP_PASSWORD is required")
        if not self.smtp_use_tls:
            errors.append("AUDIO_SMTP_USE_TLS must be true")
        if _looks_like_placeholder(self.smtp_from_email):
            errors.append("AUDIO_SMTP_FROM_EMAIL must be a real sender")
        if _looks_like_placeholder(self.database_url) or "rythm_password@" in self.database_url:
            errors.append("AUDIO_DATABASE_URL must use production credentials")
        if not self.allowed_origins or any(
            origin == "*" or not origin.startswith("https://") for origin in self.allowed_origins
        ):
            errors.append("AUDIO_CORS_ORIGINS must contain only explicit https origins")
        elif frontend_origin not in self.allowed_origins:
            errors.append("AUDIO_CORS_ORIGINS must include AUDIO_FRONTEND_URL origin")
        if not self.allowed_csrf_origins or any(
            origin == "*" or not origin.startswith("https://") for origin in self.allowed_csrf_origins
        ):
            errors.append("AUDIO_CSRF_TRUSTED_ORIGINS must contain only explicit https origins")
        elif frontend_origin not in self.allowed_csrf_origins:
            errors.append("AUDIO_CSRF_TRUSTED_ORIGINS must include AUDIO_FRONTEND_URL origin")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            errors.append("AUDIO_ALLOWED_HOSTS must contain explicit hosts")
        elif frontend_hostname not in self.trusted_hosts:
            errors.append("AUDIO_ALLOWED_HOSTS must include the frontend hostname")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def allowed_csrf_origins(self) -> set[str]:
        return {
            origin.strip().rstrip("/")
            for origin in self.csrf_trusted_origins.split(",")
            if origin.strip()
        }

    @property
    def expected_turnstile_hostnames(self) -> set[str]:
        return {
            hostname.strip().lower()
            for hostname in self.turnstile_expected_hostnames.split(",")
            if hostname.strip()
        }

    @property
    def tokyo_tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()

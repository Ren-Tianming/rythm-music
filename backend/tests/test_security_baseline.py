import pytest
from app.core.config import Settings
from app.core.security import mask_ip_address
from pydantic import ValidationError


def production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": "production",
        "app_secret": "a-production-secret-that-is-long-and-unique-1234",
        "frontend_url": "https://www.rythmmusic.site",
        "database_url": (
            "postgresql+psycopg://music_user:strong-database-secret"
            "@rythm-postgres:5432/rythm_music"
        ),
        "session_cookie_name": "__Host-rythm_session",
        "csrf_cookie_name": "__Host-rythm_csrf",
        "cookie_secure": True,
        "cors_origins": "https://www.rythmmusic.site",
        "csrf_trusted_origins": "https://www.rythmmusic.site",
        "allowed_hosts": "www.rythmmusic.site,backend",
        "turnstile_required": True,
        "turnstile_secret_key": "0x4AAAA-real-secret",
        "turnstile_expected_hostnames": "www.rythmmusic.site",
        "smtp_host": "smtp.sendgrid.net",
        "smtp_username": "apikey",
        "smtp_password": "a-real-smtp-password",
        "smtp_from_email": "noreply@rythmmusic.site",
        "smtp_use_tls": True,
    }
    values.update(overrides)
    return values


def test_production_settings_accept_explicit_secure_values() -> None:
    settings = Settings(**production_settings())
    assert settings.app_name == "RyThM Music"
    assert settings.allowed_csrf_origins == {"https://www.rythmmusic.site"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_secret", "replace-with-app-secret"),
        ("database_url", "replace-with-database-url"),
        ("turnstile_secret_key", "replace-with-turnstile-secret"),
        ("smtp_host", "smtp.example.com"),
        ("smtp_password", "changeme"),
    ],
)
def test_production_settings_reject_placeholders(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(**production_settings(**{field: value}))


def test_device_ip_masking_never_returns_full_address() -> None:
    assert mask_ip_address("203.0.113.42") == "203.0.113.*"
    assert mask_ip_address("2001:db8:abcd:1234:5678::1") == "2001:db8:abcd:1234::/64"
    assert mask_ip_address("not-an-ip") is None

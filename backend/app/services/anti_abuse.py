import httpx

from app.core.config import Settings
from app.core.errors import AppError

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(
    token: str | None,
    remote_ip: str | None,
    expected_action: str,
    settings: Settings,
) -> None:
    """Fail closed whenever Turnstile is configured or required."""
    if not settings.turnstile_secret_key:
        if settings.turnstile_required or settings.environment == "production":
            raise AppError(
                503,
                "HUMAN_VERIFICATION_UNAVAILABLE",
                "人間確認サービスが設定されていません。",
            )
        return
    if not token:
        raise AppError(400, "HUMAN_VERIFICATION_REQUIRED", "人間確認が必要です。")

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": remote_ip or "",
                },
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(
            503,
            "HUMAN_VERIFICATION_UNAVAILABLE",
            "人間確認サービスを利用できません。",
        ) from exc

    hostname = str(result.get("hostname") or "").lower()
    action = str(result.get("action") or "")
    hostname_valid = (
        not settings.expected_turnstile_hostnames
        or hostname in settings.expected_turnstile_hostnames
    )
    if not result.get("success") or not hostname_valid or action != expected_action:
        raise AppError(400, "HUMAN_VERIFICATION_FAILED", "人間確認に失敗しました。")

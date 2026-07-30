import hmac
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import Depends, Header, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import hash_api_key, token_digest, utc_now
from app.models import ApiKey, AuthSession, User

settings = get_settings()


@dataclass(frozen=True)
class CurrentAuth:
    user: User
    session: AuthSession


def _load_current_auth(request: Request, db: Session) -> CurrentAuth:
    cached = getattr(request.state, "current_auth", None)
    if isinstance(cached, CurrentAuth):
        return cached

    plain_token = request.cookies.get(settings.session_cookie_name)
    if not plain_token:
        raise AppError(401, "UNAUTHORIZED", "ログインが必要です。")

    now = utc_now()
    model = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_digest(plain_token, settings.app_secret)
        )
    )
    if model is None:
        raise AppError(401, "INVALID_SESSION", "認証セッションが無効です。")

    idle_cutoff = now - timedelta(hours=settings.session_idle_hours)
    if model.expires_at <= now or model.last_seen_at <= idle_cutoff:
        db.execute(delete(AuthSession).where(AuthSession.id == model.id))
        db.commit()
        raise AppError(401, "SESSION_EXPIRED", "認証セッションの有効期限が切れています。")

    user = db.get(User, model.user_id)
    if user is None or user.status != "ACTIVE" or not user.is_email_verified:
        db.execute(delete(AuthSession).where(AuthSession.id == model.id))
        db.commit()
        raise AppError(403, "ACCOUNT_DISABLED", "アカウントは利用できません。")

    if model.last_seen_at <= now - timedelta(seconds=settings.session_touch_interval_seconds):
        model.last_seen_at = now
        db.commit()

    auth = CurrentAuth(user=user, session=model)
    request.state.current_auth = auth
    return auth


def get_current_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> CurrentAuth:
    return _load_current_auth(request, db)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    return _load_current_auth(request, db).user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    if not request.cookies.get(settings.session_cookie_name):
        return None
    try:
        return _load_current_auth(request, db).user
    except AppError:
        return None


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise AppError(403, "FORBIDDEN", "管理者権限が必要です。")
    return user


def get_api_or_current_user(
    request: Request,
    api_key_value: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    if api_key_value:
        key = db.scalar(
            select(ApiKey).where(
                ApiKey.key_hash == hash_api_key(api_key_value),
                ApiKey.status == "ACTIVE",
            )
        )
        if key is None:
            raise AppError(401, "INVALID_API_KEY", "APIキーが無効です。")
        user = db.get(User, key.user_id)
        if user is None or user.status != "ACTIVE":
            raise AppError(403, "ACCOUNT_DISABLED", "アカウントは利用できません。")
        return user
    return _load_current_auth(request, db).user


def verify_csrf(
    request: Request,
    csrf_header: str | None = Header(default=None, alias=settings.csrf_header_name),
    db: Session = Depends(get_db),
) -> None:
    """Validate a double-submit token hashed into this exact server session."""
    auth = _load_current_auth(request, db)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
        or not hmac.compare_digest(
            token_digest(csrf_header, settings.app_secret),
            auth.session.csrf_hash,
        )
    ):
        raise AppError(403, "CSRF_VALIDATION_FAILED", "CSRF 検証に失敗しました。")

    source = request.headers.get("origin") or request.headers.get("referer")
    if source:
        parsed = urlparse(source)
        source_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if source_origin not in settings.allowed_csrf_origins:
            raise AppError(
                403,
                "CSRF_ORIGIN_INVALID",
                "リクエスト元を確認できませんでした。",
            )
    elif settings.environment == "production":
        raise AppError(
            403,
            "CSRF_ORIGIN_REQUIRED",
            "リクエスト元の情報が必要です。",
        )


def verify_csrf_or_api_key(
    request: Request,
    csrf_header: str | None = Header(default=None, alias=settings.csrf_header_name),
    db: Session = Depends(get_db),
) -> None:
    if request.headers.get("x-api-key"):
        return
    verify_csrf(request, csrf_header, db)

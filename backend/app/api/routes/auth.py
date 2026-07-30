from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentAuth, get_current_auth, get_current_user, verify_csrf
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.observability import request_id_var
from app.core.rate_limit import get_rate_limiter
from app.core.security import hash_password, mask_ip_address, utc_now, verify_password
from app.models import AuthSession, User
from app.schemas.api import (
    BrowserSessionResponse,
    ForgotPasswordRequest,
    LoginRequest,
    Message,
    PasswordChange,
    ResetPasswordRequest,
    SessionResponse,
    UserCreate,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.anti_abuse import verify_turnstile
from app.services.auth import (
    SessionGrant,
    login_user,
    record_audit,
    register_user,
    request_password_reset,
    resend_verification,
    reset_password,
    revoke_all_sessions,
    revoke_session,
    verify_email,
)
from app.services.mail import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["認証"])
settings = get_settings()
rate_limiter = get_rate_limiter()


def client_metadata(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    result = rate_limiter.check(key, limit, window_seconds)
    if not result.allowed:
        raise AppError(
            429,
            "RATE_LIMITED",
            "リクエスト数が上限を超えました。しばらくしてから再試行してください。",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


def _cookie_secure() -> bool:
    return settings.cookie_secure or settings.environment.lower() == "production"


def _set_auth_cookies(response: Response, grant: SessionGrant) -> SessionResponse:
    max_age = settings.session_absolute_days * 24 * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        grant.session_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.cookie_samesite,
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        grant.csrf_token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=settings.cookie_samesite,
        path="/",
        max_age=max_age,
    )
    # Invalidate cookies from the legacy JWT/refresh-token implementation.
    for legacy_name in ("rythm_session", "rythm_csrf", "rythm_refresh"):
        if legacy_name not in {
            settings.session_cookie_name,
            settings.csrf_cookie_name,
        }:
            response.delete_cookie(
                legacy_name,
                path="/",
                secure=_cookie_secure(),
                samesite=settings.cookie_samesite,
            )
    return SessionResponse(
        user=grant.user,
        daily_bonus_awarded=grant.daily_bonus_awarded,
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in {
        settings.session_cookie_name,
        settings.csrf_cookie_name,
        "rythm_session",
        "rythm_csrf",
        "rythm_refresh",
    }:
        response.delete_cookie(name, path="/", secure=_cookie_secure(), samesite=settings.cookie_samesite)


@router.post("/register", response_model=Message, status_code=202)
def register(
    payload: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Message:
    _, ip_address = client_metadata(request)
    _enforce_rate_limit(
        f"register:ip:{ip_address or 'unknown'}",
        settings.registration_rate_limit_per_hour,
        3600,
    )
    verify_turnstile(payload.turnstile_token, ip_address, "register", settings)
    email, verification_token = register_user(db, payload, ip_address)
    if email and verification_token:
        background_tasks.add_task(
            send_verification_email,
            email,
            verification_token,
            settings,
        )
    return Message(
        message="登録を受け付けました。該当する場合は確認メールを送信します。"
    )


@router.post("/resend-verification", response_model=Message)
def resend_verification_email(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Message:
    _, ip_address = client_metadata(request)
    normalized = str(payload.email).strip().casefold()
    _enforce_rate_limit(
        f"resend:email:{normalized}",
        settings.email_action_rate_limit_per_hour,
        3600,
    )
    _enforce_rate_limit(
        f"resend:ip:{ip_address or 'unknown'}",
        settings.email_action_ip_rate_limit_per_hour,
        3600,
    )
    verify_turnstile(
        payload.turnstile_token,
        ip_address,
        "resend-verification",
        settings,
    )
    email, verification_token = resend_verification(db, payload.email)
    if email and verification_token:
        background_tasks.add_task(
            send_verification_email,
            email,
            verification_token,
            settings,
        )
    return Message(message="該当する場合は確認メールを送信します。")


@router.post("/verify-email", response_model=Message)
def confirm_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Message:
    user_agent, ip_address = client_metadata(request)
    _enforce_rate_limit(
        f"verify:ip:{ip_address or 'unknown'}",
        settings.verification_rate_limit_per_hour,
        3600,
    )
    try:
        verify_email(db, payload.token)
    except AppError as exc:
        record_audit(
            db,
            "email_verification_failed",
            result="failure",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id_var.get(),
            metadata_redacted={"reason": exc.code},
        )
        db.commit()
        raise
    return Message(message="メールアドレスを確認しました。ログインできます。")


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_agent, ip_address = client_metadata(request)
    normalized = str(payload.email).strip().casefold()
    login_key = f"{normalized}:{ip_address or 'unknown'}"
    _enforce_rate_limit(
        f"login:{login_key}",
        settings.login_rate_limit_per_ten_minutes,
        600,
    )
    backoff = rate_limiter.check_login_backoff(login_key)
    if not backoff.allowed:
        raise AppError(
            429,
            "LOGIN_BACKOFF",
            "ログインを再試行するまで少しお待ちください。",
            headers={"Retry-After": str(backoff.retry_after_seconds)},
        )
    verify_turnstile(payload.turnstile_token, ip_address, "login", settings)
    try:
        grant = login_user(db, payload, user_agent, ip_address)
    except AppError as exc:
        if exc.code in {
            "INVALID_CREDENTIALS",
            "EMAIL_NOT_VERIFIED",
            "ACCOUNT_DISABLED",
        }:
            if exc.code == "INVALID_CREDENTIALS":
                rate_limiter.register_login_failure(login_key)
            user_id = db.scalar(select(User.id).where(User.email == normalized))
            record_audit(
                db,
                "login_failed",
                user_id=user_id,
                result="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id_var.get(),
                metadata_redacted={"reason": exc.code},
            )
            db.commit()
        raise
    rate_limiter.clear_login_failures(login_key)
    record_audit(
        db,
        "login_succeeded",
        user_id=grant.user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id_var.get(),
    )
    db.commit()
    return _set_auth_cookies(response, grant)


@router.post("/forgot-password", response_model=Message)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Message:
    _, ip_address = client_metadata(request)
    normalized = str(payload.email).strip().casefold()
    _enforce_rate_limit(
        f"forgot:email:{normalized}",
        settings.email_action_rate_limit_per_hour,
        3600,
    )
    _enforce_rate_limit(
        f"forgot:ip:{ip_address or 'unknown'}",
        settings.email_action_ip_rate_limit_per_hour,
        3600,
    )
    verify_turnstile(
        payload.turnstile_token,
        ip_address,
        "forgot-password",
        settings,
    )
    email, reset_token = request_password_reset(db, payload.email)
    if email and reset_token:
        background_tasks.add_task(
            send_password_reset_email,
            email,
            reset_token,
            settings,
        )
    return Message(message="該当する場合はパスワード再設定メールを送信します。")


@router.post("/reset-password", response_model=Message)
def complete_password_reset(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Message:
    user_agent, ip_address = client_metadata(request)
    _enforce_rate_limit(
        f"reset:ip:{ip_address or 'unknown'}",
        settings.email_action_ip_rate_limit_per_hour,
        3600,
    )
    try:
        reset_password(
            db,
            payload,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id_var.get(),
        )
    except AppError as exc:
        record_audit(
            db,
            "password_reset_failed",
            result="failure",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id_var.get(),
            metadata_redacted={"reason": exc.code},
        )
        db.commit()
        raise
    _clear_auth_cookies(response)
    return Message(message="パスワードを再設定しました。すべての端末からログアウトしました。")


@router.post("/logout", response_model=Message)
def logout(
    response: Response,
    _: None = Depends(verify_csrf),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Message:
    record_audit(
        db,
        "logout",
        user_id=auth.user.id,
        request_id=request_id_var.get(),
    )
    revoke_session(db, auth.user.id, auth.session.id)
    _clear_auth_cookies(response)
    return Message(message="ログアウトしました。")


@router.post("/logout-all", response_model=Message)
def logout_all(
    response: Response,
    _: None = Depends(verify_csrf),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Message:
    record_audit(
        db,
        "logout_all",
        user_id=auth.user.id,
        request_id=request_id_var.get(),
    )
    revoke_all_sessions(db, auth.user.id)
    _clear_auth_cookies(response)
    return Message(message="すべての端末のセッションをログアウトしました。")


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/sessions", response_model=list[BrowserSessionResponse])
def list_sessions(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[BrowserSessionResponse]:
    now = utc_now()
    idle_cutoff = now - timedelta(hours=settings.session_idle_hours)
    sessions = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == auth.user.id,
            AuthSession.expires_at > now,
            AuthSession.last_seen_at > idle_cutoff,
        )
        .order_by(AuthSession.last_seen_at.desc())
    ).all()
    return [
        BrowserSessionResponse(
            id=session.id,
            user_agent=session.user_agent,
            ip_address=mask_ip_address(session.ip_address),
            last_seen_at=session.last_seen_at,
            created_at=session.created_at,
            current=session.id == auth.session.id,
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", response_model=Message)
def delete_session(
    session_id: UUID,
    response: Response,
    _: None = Depends(verify_csrf),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Message:
    session_key = str(session_id)
    if not revoke_session(db, auth.user.id, session_key):
        raise AppError(404, "SESSION_NOT_FOUND", "セッションが見つかりません。")
    record_audit(
        db,
        "session_revoked",
        user_id=auth.user.id,
        request_id=request_id_var.get(),
        metadata_redacted={"current": session_key == auth.session.id},
    )
    db.commit()
    if session_key == auth.session.id:
        _clear_auth_cookies(response)
    return Message(message="端末セッションを失効させました。")


@router.patch("/password", response_model=Message)
def change_password(
    payload: PasswordChange,
    response: Response,
    _: None = Depends(verify_csrf),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Message:
    if not verify_password(payload.current_password, auth.user.hashed_password):
        record_audit(
            db,
            "password_change_failed",
            user_id=auth.user.id,
            result="failure",
            request_id=request_id_var.get(),
        )
        db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "現在のパスワードが不正です。")
    if verify_password(payload.new_password, auth.user.hashed_password):
        record_audit(
            db,
            "password_change_failed",
            user_id=auth.user.id,
            result="failure",
            request_id=request_id_var.get(),
            metadata_redacted={"reason": "PASSWORD_REUSE_NOT_ALLOWED"},
        )
        db.commit()
        raise AppError(422, "PASSWORD_REUSE_NOT_ALLOWED", "新しいパスワードを指定してください。")
    auth.user.hashed_password = hash_password(payload.new_password)
    db.flush()
    record_audit(
        db,
        "password_changed",
        user_id=auth.user.id,
        request_id=request_id_var.get(),
    )
    revoke_all_sessions(db, auth.user.id)
    _clear_auth_cookies(response)
    return Message(message="パスワードを更新しました。すべての端末からログアウトしました。")

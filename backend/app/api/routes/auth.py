from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentAuth, get_current_auth, get_current_user, verify_csrf
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import hash_password, utc_now, verify_password
from app.models import AuthSession, User
from app.schemas.api import (
    BrowserSessionResponse,
    LoginRequest,
    Message,
    PasswordChange,
    SessionResponse,
    UserCreate,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.anti_abuse import verify_turnstile
from app.services.auth import (
    SessionGrant,
    login_user,
    register_user,
    revoke_all_sessions,
    revoke_session,
    verify_email,
)
from app.services.mail import send_verification_email

router = APIRouter(prefix="/auth", tags=["認証"])
settings = get_settings()


def client_metadata(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


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
    response.delete_cookie("rythm_refresh", path="/")
    return SessionResponse(
        user=grant.user,
        daily_bonus_awarded=grant.daily_bonus_awarded,
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (
        settings.session_cookie_name,
        settings.csrf_cookie_name,
        "rythm_refresh",
    ):
        response.delete_cookie(name, path="/", secure=_cookie_secure(), samesite=settings.cookie_samesite)


@router.post("/register", response_model=Message, status_code=202)
def register(
    payload: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Message:
    _, ip_address = client_metadata(request)
    verify_turnstile(payload.turnstile_token, ip_address, "register", settings)
    email, verification_token = register_user(db, payload)
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


@router.post("/verify-email", response_model=Message)
def confirm_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> Message:
    verify_email(db, payload.token)
    return Message(message="メールアドレスを確認しました。ログインできます。")


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_agent, ip_address = client_metadata(request)
    verify_turnstile(payload.turnstile_token, ip_address, "login", settings)
    return _set_auth_cookies(response, login_user(db, payload, user_agent, ip_address))


@router.post("/logout", response_model=Message)
def logout(
    response: Response,
    _: None = Depends(verify_csrf),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Message:
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
            ip_address=session.ip_address,
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
        raise AppError(401, "INVALID_CREDENTIALS", "現在のパスワードが不正です。")
    auth.user.hashed_password = hash_password(payload.new_password)
    db.flush()
    revoke_all_sessions(db, auth.user.id)
    _clear_auth_cookies(response)
    return Message(message="パスワードを更新しました。すべての端末からログアウトしました。")

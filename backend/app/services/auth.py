from dataclasses import dataclass
from datetime import UTC, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    hash_password,
    new_token,
    password_needs_rehash,
    token_digest,
    utc_now,
    verify_password,
)
from app.models import (
    AuditLog,
    AuthSession,
    DailyLoginReward,
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserConsent,
)
from app.schemas.api import LoginRequest, ResetPasswordRequest, UserCreate, UserResponse
from app.services.points import apply_points

settings = get_settings()
DUMMY_PASSWORD_HASH = hash_password(new_token(32))


def record_audit(
    db: Session,
    event_type: str,
    *,
    user_id: int | None = None,
    result: str = "success",
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    metadata_redacted: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            event_type=event_type,
            result=result,
            ip_address=ip_address[:64] if ip_address else None,
            user_agent=user_agent[:512] if user_agent else None,
            request_id=request_id[:80] if request_id else None,
            metadata_redacted=metadata_redacted,
        )
    )


@dataclass(frozen=True)
class SessionGrant:
    session_token: str
    csrf_token: str
    user: UserResponse
    daily_bonus_awarded: int = 0


def _normalized_email(email: object) -> str:
    return str(email).strip().casefold()


def _issue_verification_token(db: Session, user: User) -> str:
    db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    plain_token = new_token(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_digest(plain_token, settings.app_secret),
            expires_at=utc_now()
            + timedelta(hours=settings.email_verification_expire_hours),
        )
    )
    db.flush()
    return plain_token


def _verification_on_cooldown(db: Session, user_id: int) -> bool:
    latest_created_at = db.scalar(
        select(EmailVerificationToken.created_at)
        .where(EmailVerificationToken.user_id == user_id)
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    return bool(
        latest_created_at
        and latest_created_at
        > utc_now()
        - timedelta(seconds=settings.email_verification_resend_seconds)
    )


def _issue_session(
    db: Session,
    user: User,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[str, str]:
    now = utc_now()
    session_token = new_token(32)
    csrf_token = new_token(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_digest(session_token, settings.app_secret),
            csrf_hash=token_digest(csrf_token, settings.app_secret),
            user_agent=user_agent[:512] if user_agent else None,
            ip_address=ip_address[:64] if ip_address else None,
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.session_absolute_days),
        )
    )
    db.flush()
    return session_token, csrf_token


def register_user(
    db: Session,
    payload: UserCreate,
    ip_address: str | None = None,
) -> tuple[str | None, str | None]:
    if payload.password != payload.password_confirmation:
        raise AppError(422, "PASSWORD_CONFIRMATION_MISMATCH", "パスワード確認が一致しません。")

    email = _normalized_email(payload.email)
    if payload.terms_version != settings.terms_version:
        raise AppError(422, "CONSENT_REQUIRED", "現在の利用規約への同意が必要です。")
    existing = db.scalar(select(User).where(User.email == email).with_for_update())
    if existing is not None:
        # Match the Argon2 work performed for a new account to reduce timing enumeration.
        hash_password(payload.password)
        if (
            existing.status == "PENDING_VERIFICATION"
            and not existing.is_email_verified
            and not _verification_on_cooldown(db, existing.id)
        ):
            plain_token = _issue_verification_token(db, existing)
            db.commit()
            return existing.email, plain_token
        # Indistinguishable responses prevent registration-based account enumeration.
        return None, None

    user = User(
        email=email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        locale=payload.locale,
        status="PENDING_VERIFICATION",
        is_email_verified=False,
    )
    db.add(user)
    try:
        db.flush()
        db.add(
            UserConsent(
                user_id=user.id,
                document_type="terms",
                document_version=payload.terms_version,
                ip_address=ip_address,
            )
        )
        record_audit(
            db,
            "user_registered",
            user_id=user.id,
            ip_address=ip_address,
        )
        plain_token = _issue_verification_token(db, user)
        db.commit()
        return user.email, plain_token
    except IntegrityError:
        db.rollback()
        return None, None


def verify_email(db: Session, plain_token: str) -> UserResponse:
    now = utc_now()
    token = db.scalar(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == token_digest(plain_token, settings.app_secret),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        .with_for_update()
    )
    if token is None:
        raise AppError(
            400,
            "INVALID_EMAIL_VERIFICATION_TOKEN",
            "メール確認リンクが無効か、有効期限が切れています。",
        )

    user = db.scalar(select(User).where(User.id == token.user_id).with_for_update())
    if user is None:
        raise AppError(400, "INVALID_EMAIL_VERIFICATION_TOKEN", "メール確認リンクが無効です。")

    if not user.is_email_verified:
        user.is_email_verified = True
        user.email_verified_at = now
        user.status = "ACTIVE"
        if settings.registration_bonus:
            apply_points(
                db,
                user.id,
                settings.registration_bonus,
                "REGISTER_BONUS",
                "新規登録ボーナス",
            )

    token.used_at = now
    record_audit(db, "email_verified", user_id=user.id)
    db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != token.id,
        )
    )
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def login_user(
    db: Session,
    payload: LoginRequest,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> SessionGrant:
    email = _normalized_email(payload.email)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise AppError(401, "INVALID_CREDENTIALS", "メールアドレスまたはパスワードが不正です。")
    if not verify_password(payload.password, user.hashed_password):
        raise AppError(401, "INVALID_CREDENTIALS", "メールアドレスまたはパスワードが不正です。")
    if not user.is_email_verified or user.status == "PENDING_VERIFICATION":
        raise AppError(403, "EMAIL_NOT_VERIFIED", "先にメールアドレスを確認してください。")
    if user.status != "ACTIVE":
        raise AppError(403, "ACCOUNT_DISABLED", "アカウントは停止されています。")

    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)

    today = utc_now().replace(tzinfo=UTC).astimezone(settings.tokyo_tz).date()
    daily_bonus = 0
    if not db.scalar(
        select(DailyLoginReward.id).where(
            DailyLoginReward.user_id == user.id,
            DailyLoginReward.reward_date == today,
        )
    ):
        db.add(
            DailyLoginReward(
                user_id=user.id,
                reward_date=today,
                points_awarded=settings.daily_login_bonus,
            )
        )
        if settings.daily_login_bonus:
            apply_points(
                db,
                user.id,
                settings.daily_login_bonus,
                "DAILY_LOGIN_BONUS",
                "デイリーログインボーナス",
            )
        daily_bonus = settings.daily_login_bonus

    user.last_login_at = utc_now()
    session_token, csrf_token = _issue_session(db, user, user_agent, ip_address)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request may have inserted today's unique login reward.
        db.rollback()
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or user.status != "ACTIVE":
            raise AppError(401, "INVALID_CREDENTIALS", "メールアドレスまたはパスワードが不正です。") from None
        daily_bonus = 0
        user.last_login_at = utc_now()
        session_token, csrf_token = _issue_session(db, user, user_agent, ip_address)
        db.commit()
    db.refresh(user)
    return SessionGrant(
        session_token=session_token,
        csrf_token=csrf_token,
        user=UserResponse.model_validate(user),
        daily_bonus_awarded=daily_bonus,
    )


def request_password_reset(
    db: Session,
    email_value: object,
) -> tuple[str | None, str | None]:
    email = _normalized_email(email_value)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None or user.status != "ACTIVE" or not user.is_email_verified:
        return None, None

    now = utc_now()
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    plain_token = new_token(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_digest(plain_token, settings.app_secret),
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    record_audit(db, "password_reset_requested", user_id=user.id)
    db.commit()
    return user.email, plain_token


def resend_verification(
    db: Session,
    email_value: object,
) -> tuple[str | None, str | None]:
    email = _normalized_email(email_value)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if (
        user is None
        or user.status != "PENDING_VERIFICATION"
        or user.is_email_verified
        or _verification_on_cooldown(db, user.id)
    ):
        return None, None
    plain_token = _issue_verification_token(db, user)
    record_audit(db, "email_verification_resent", user_id=user.id)
    db.commit()
    return user.email, plain_token


def reset_password(
    db: Session,
    payload: ResetPasswordRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> int:
    now = utc_now()
    token = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash
            == token_digest(payload.token, settings.app_secret),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if token is None:
        raise AppError(
            400,
            "INVALID_PASSWORD_RESET_TOKEN",
            "パスワード再設定リンクが無効か、有効期限が切れています。",
        )
    user = db.scalar(select(User).where(User.id == token.user_id).with_for_update())
    if user is None:
        raise AppError(400, "INVALID_PASSWORD_RESET_TOKEN", "パスワード再設定リンクが無効です。")
    if verify_password(payload.password, user.hashed_password):
        raise AppError(422, "PASSWORD_REUSE_NOT_ALLOWED", "新しいパスワードを指定してください。")

    user.hashed_password = hash_password(payload.password)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    record_audit(
        db,
        "password_reset",
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    db.commit()
    return user.id


def revoke_session(db: Session, user_id: int, session_id: str) -> bool:
    result = db.execute(
        delete(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
        )
    )
    db.commit()
    return bool(result.rowcount)


def revoke_all_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.commit()

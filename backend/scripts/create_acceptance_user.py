import os

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import (
    hash_password,
    utc_now,
    validate_display_name,
    validate_password_strength,
)
from app.models import (
    AuditLog,
    AuthSession,
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserConsent,
)
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import delete, select

DEFAULT_ACCEPTANCE_EMAIL = "acceptance@example.com"
LEGACY_ACCEPTANCE_EMAIL = "acceptance@local.test"
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def required_environment_value(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} を設定してください。")
    return value


def main() -> None:
    """ローカル受入試験用ユーザーを再実行可能な形で作成する。"""
    settings = get_settings()
    raw_email = os.environ.get("ACCEPTANCE_EMAIL", DEFAULT_ACCEPTANCE_EMAIL)
    username = validate_display_name(os.environ.get("ACCEPTANCE_USERNAME", "本地验收账号"))
    password = required_environment_value("ACCEPTANCE_PASSWORD")

    try:
        email = str(EMAIL_ADAPTER.validate_python(raw_email.strip().casefold()))
    except ValidationError as exc:
        raise SystemExit("ACCEPTANCE_EMAIL にログイン可能なメールアドレスを設定してください。") from exc
    if not 12 <= len(password) <= 128:
        raise SystemExit("ACCEPTANCE_PASSWORD は 12〜128 文字で設定してください。")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    now = utc_now()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        action = "updated"
        if user is None and email == DEFAULT_ACCEPTANCE_EMAIL:
            user = db.scalar(select(User).where(User.email == LEGACY_ACCEPTANCE_EMAIL).with_for_update())
            if user is not None:
                user.email = email
                action = "migrated"
        if user is None:
            action = "created"
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                locale="zh-CN",
                role="USER",
                status="ACTIVE",
                is_email_verified=True,
                email_verified_at=now,
            )
            db.add(user)
            db.flush()
        else:
            user.username = username
            user.hashed_password = hash_password(password)
            user.status = "ACTIVE"
            user.is_email_verified = True
            user.email_verified_at = user.email_verified_at or now
            db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
            db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
            db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))

        existing_consent = db.scalar(
            select(UserConsent.id).where(
                UserConsent.user_id == user.id,
                UserConsent.document_type == "terms",
                UserConsent.document_version == settings.terms_version,
            )
        )
        if existing_consent is None:
            db.add(
                UserConsent(
                    user_id=user.id,
                    document_type="terms",
                    document_version=settings.terms_version,
                    ip_address="127.0.0.1",
                )
            )

        db.add(
            AuditLog(
                user_id=user.id,
                event_type="local_acceptance_user_seeded",
                result="success",
                ip_address="127.0.0.1",
                metadata_redacted={
                    "source": "local_acceptance_seed",
                    "action": action,
                },
            )
        )
        db.commit()

    print(f"ローカル受入試験用ユーザーを作成または更新しました。 email={email} terms_version={settings.terms_version}")


if __name__ == "__main__":
    main()

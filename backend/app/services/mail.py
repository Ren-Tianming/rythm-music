import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import Settings

logger = logging.getLogger("audio_analysis_system.mail")


def build_verification_url(token: str, settings: Settings) -> str:
    """Keep one-time credentials out of HTTP request targets and referrers."""
    return f"{settings.frontend_url.rstrip('/')}/#verify={quote(token, safe='')}"


def build_password_reset_url(token: str, settings: Settings) -> str:
    return f"{settings.frontend_url.rstrip('/')}/#reset={quote(token, safe='')}"


def _send_email(
    to_email: str,
    subject: str,
    body: str,
    settings: Settings,
) -> None:
    if not settings.smtp_host:
        if settings.environment == "production":
            raise RuntimeError("SMTP is not configured")
        logger.warning("Development email to=%s subject=%s body=%s", to_email, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
        if settings.smtp_use_tls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


def send_verification_email(to_email: str, token: str, settings: Settings) -> None:
    url = build_verification_url(token, settings)
    _send_email(
        to_email,
        "Verify your RyThM Music account",
        "Complete your RyThM Music registration using this one-time link. "
        f"It expires in {settings.email_verification_expire_hours} hours.\n\n{url}",
        settings,
    )


def send_password_reset_email(to_email: str, token: str, settings: Settings) -> None:
    url = build_password_reset_url(token, settings)
    _send_email(
        to_email,
        "Reset your RyThM Music password",
        "Use this one-time link to reset your RyThM Music password. "
        f"It expires in {settings.password_reset_expire_minutes} minutes.\n\n{url}",
        settings,
    )

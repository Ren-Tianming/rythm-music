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


def send_verification_email(to_email: str, token: str, settings: Settings) -> None:
    url = build_verification_url(token, settings)
    if not settings.smtp_host:
        if settings.environment == "production":
            raise RuntimeError("SMTP is not configured")
        logger.warning("Development verification email to=%s url=%s", to_email, url)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = "Verify your RyThM Music account"
    message.set_content(
        "Complete your RyThM Music registration using this one-time link. "
        f"It expires in {settings.email_verification_expire_hours} hours.\n\n{url}"
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
        if settings.smtp_use_tls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)

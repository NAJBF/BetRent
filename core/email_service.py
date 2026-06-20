import logging
import random
import string

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL = 600  # 10 minutes


def _generate_otp():
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def _otp_cache_key(purpose, email):
    return f"otp:{purpose}:{email.lower()}"


def store_otp(email, purpose):
    """Generate and store OTP in cache. Returns the OTP code."""
    otp = _generate_otp()
    cache.set(_otp_cache_key(purpose, email), otp, OTP_TTL)
    return otp


def verify_otp(email, purpose, code):
    """Verify OTP and delete on success."""
    key = _otp_cache_key(purpose, email)
    stored = cache.get(key)
    if stored and stored == code:
        cache.delete(key)
        return True
    return False


def _is_smtp_configured():
    return bool(getattr(settings, "EMAIL_HOST_USER", "") and getattr(settings, "EMAIL_HOST_PASSWORD", ""))


def send_otp_email(email, purpose, otp, extra_context=None):
    """
    Send OTP email. Never raises — registration/auth must not fail if mail is down.
    Returns True if sent successfully, False otherwise.
    """
    extra_context = extra_context or {}
    plan_name = extra_context.get("plan_name", "")
    role = extra_context.get("role", "")

    if purpose == "register":
        subject = "BetRent — Verify Your Email"
        if plan_name:
            body = (
                f"Welcome to BetRent!\n\n"
                f"Your verification code is: {otp}\n\n"
                f"Selected plan: {plan_name}\n"
                f"Role: {role}\n\n"
                f"This code expires in 10 minutes.\n"
            )
        else:
            body = (
                f"Welcome to BetRent!\n\n"
                f"Your verification code is: {otp}\n\n"
                f"This code expires in 10 minutes.\n"
            )
    elif purpose == "reset_password":
        subject = "BetRent — Password Reset Code"
        body = (
            f"You requested a password reset.\n\n"
            f"Your reset code is: {otp}\n\n"
            f"This code expires in 10 minutes.\n"
            f"If you did not request this, ignore this email.\n"
        )
    else:
        subject = "BetRent — Verification Code"
        body = f"Your verification code is: {otp}\n\nThis code expires in 10 minutes.\n"

    from_email = settings.DEFAULT_FROM_EMAIL

    if not _is_smtp_configured():
        logger.warning(
            "SMTP not configured — OTP for %s (purpose=%s) not emailed. "
            "Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD on the server.",
            email,
            purpose,
        )
        return False

    try:
        sent = send_mail(
            subject,
            body,
            from_email,
            [email],
            fail_silently=True,
        )
        if sent:
            logger.info("OTP email sent to %s (purpose=%s)", email, purpose)
            return True
        logger.warning("OTP email not sent to %s (purpose=%s) — send_mail returned 0", email, purpose)
        return False
    except Exception as exc:
        logger.error("Email send failed for %s (purpose=%s): %s", email, purpose, exc)
        return False

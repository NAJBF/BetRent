import logging
import random
import string

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection

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


def get_email_debug_info():
    """Safe config summary for API responses (no password)."""
    return {
        "backend": settings.EMAIL_BACKEND,
        "host": settings.EMAIL_HOST,
        "port": settings.EMAIL_PORT,
        "use_tls": getattr(settings, "EMAIL_USE_TLS", False),
        "use_ssl": getattr(settings, "EMAIL_USE_SSL", False),
        "user": settings.EMAIL_HOST_USER or None,
        "from_email": settings.DEFAULT_FROM_EMAIL,
        "password_set": bool(settings.EMAIL_HOST_PASSWORD),
    }


def _build_otp_message(purpose, otp, extra_context=None):
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

    return subject, body


def _smtp_connection_options():
    """Primary settings + Gmail fallback (465 SSL if 587 TLS fails, and vice versa)."""
    host = settings.EMAIL_HOST
    timeout = getattr(settings, "EMAIL_TIMEOUT", 8)

    primary = {
        "host": host,
        "port": settings.EMAIL_PORT,
        "use_tls": getattr(settings, "EMAIL_USE_TLS", False),
        "use_ssl": getattr(settings, "EMAIL_USE_SSL", False),
        "timeout": timeout,
    }

    options = [primary]

    if host == "smtp.gmail.com":
        if primary["port"] == 587:
            options.append({
                "host": host,
                "port": 465,
                "use_tls": False,
                "use_ssl": True,
                "timeout": timeout,
            })
        elif primary["port"] == 465:
            options.append({
                "host": host,
                "port": 587,
                "use_tls": True,
                "use_ssl": False,
                "timeout": timeout,
            })

    return options


def _send_via_smtp(to_email, subject, body, smtp_opts):
    from_email = settings.DEFAULT_FROM_EMAIL
    connection = get_connection(
        backend=settings.EMAIL_BACKEND,
        host=smtp_opts["host"],
        port=smtp_opts["port"],
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=smtp_opts["use_tls"],
        use_ssl=smtp_opts["use_ssl"],
        timeout=smtp_opts["timeout"],
        fail_silently=False,
    )
    connection.open()
    try:
        msg = EmailMessage(subject, body, from_email, [to_email], connection=connection)
        return msg.send()
    finally:
        connection.close()


def send_otp_email(email, purpose, otp, extra_context=None):
    """
    Send OTP email. Tries SMTP with fallbacks.
    Returns dict: {sent, via, error, debug_otp}
    """
    subject, body = _build_otp_message(purpose, otp, extra_context)

    if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
        logger.info("Console backend — OTP for %s: %s", email, otp)
        return {
            "sent": True,
            "via": "console",
            "error": None,
            "debug_otp": otp if settings.DEBUG else None,
        }

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        error = "EMAIL_HOST_USER or EMAIL_HOST_PASSWORD is missing."
        if settings.DEBUG:
            logger.warning("DEV OTP for %s: %s (%s)", email, otp, error)
            return {"sent": True, "via": "debug", "error": error, "debug_otp": otp}
        raise RuntimeError(f"{error} Config: {get_email_debug_info()}")

    errors = []
    for opts in _smtp_connection_options():
        label = f"{opts['host']}:{opts['port']} tls={opts['use_tls']} ssl={opts['use_ssl']}"
        try:
            sent = _send_via_smtp(email, subject, body, opts)
            if sent:
                logger.info("OTP sent to %s via %s", email, label)
                return {"sent": True, "via": label, "error": None, "debug_otp": None}
            errors.append(f"{label}: send returned 0")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            logger.warning("SMTP attempt failed (%s): %s", label, exc)

    combined = "; ".join(errors)
    if settings.DEBUG:
        logger.warning("SMTP failed for %s — DEV OTP: %s | Errors: %s", email, otp, combined)
        return {
            "sent": True,
            "via": "debug",
            "error": combined,
            "debug_otp": otp,
        }

    raise RuntimeError(combined)

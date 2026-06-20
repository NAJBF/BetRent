import json
import logging
import random
import string
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone

from core.models import EmailOTP

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL = 600  # 10 minutes


def _generate_otp():
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def _otp_cache_key(purpose, email):
    return f"otp:{purpose}:{email.lower()}"


def store_otp(email, purpose):
    otp = _generate_otp()
    cache.set(_otp_cache_key(purpose, email), otp, OTP_TTL)

    EmailOTP.objects.filter(
        email=email.lower(),
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)

    EmailOTP.objects.create(
        email=email.lower(),
        purpose=purpose,
        code=otp,
        expires_at=timezone.now() + timedelta(seconds=OTP_TTL),
    )
    return otp


def verify_otp(email, purpose, code):
    key = _otp_cache_key(purpose, email)
    stored = cache.get(key)
    if stored and stored == code:
        cache.delete(key)
        EmailOTP.objects.filter(
            email=email.lower(),
            purpose=purpose,
            code=code,
            is_used=False,
        ).update(is_used=True)
        return True
    return False


def _active_provider():
    if getattr(settings, "BREVO_API_KEY", "").strip():
        return "brevo"
    if getattr(settings, "RESEND_API_KEY", "").strip():
        return "resend"
    if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
        return "smtp"
    return "none"


def get_email_debug_info():
    return {
        "provider": _active_provider(),
        "brevo_configured": bool(getattr(settings, "BREVO_API_KEY", "")),
        "brevo_sender": getattr(settings, "BREVO_SENDER_EMAIL", None),
        "resend_configured": bool(getattr(settings, "RESEND_API_KEY", "")),
        "from_email": (
            getattr(settings, "BREVO_SENDER_EMAIL", None)
            or getattr(settings, "RESEND_FROM_EMAIL", None)
            or settings.DEFAULT_FROM_EMAIL
        ),
        "smtp_host": settings.EMAIL_HOST,
        "smtp_port": settings.EMAIL_PORT,
        "smtp_user": settings.EMAIL_HOST_USER or None,
        "smtp_password_set": bool(settings.EMAIL_HOST_PASSWORD),
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


def _send_via_brevo(to_email, subject, body):
    api_key = getattr(settings, "BREVO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not configured.")

    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "").strip()
    if not sender_email:
        raise RuntimeError("BREVO_SENDER_EMAIL is not configured.")

    sender_name = getattr(settings, "BREVO_SENDER_NAME", "BetRent").strip() or "BetRent"
    payload = json.dumps({
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
        "htmlContent": f"<pre style='font-family:sans-serif;font-size:16px'>{body}</pre>",
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Brevo API returned status {response.status}")
            raw = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {}
            message_id = data.get("messageId")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brevo API error ({exc.code}): {detail}") from exc

    logger.info(
        "OTP queued via Brevo to %s from %s (messageId=%s)",
        to_email,
        sender_email,
        message_id,
    )
    return message_id


def _send_via_resend(to_email, subject, body):
    import resend

    api_key = getattr(settings, "RESEND_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    from_email = (
        getattr(settings, "RESEND_FROM_EMAIL", "").strip()
        or settings.DEFAULT_FROM_EMAIL
    )

    resend.api_key = api_key
    resend.Emails.send({
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "text": body,
        "html": f"<pre style='font-family:sans-serif;font-size:16px'>{body}</pre>",
    })

    logger.info("OTP sent to %s via Resend", to_email)
    return True


def _send_via_smtp(to_email, subject, body):
    from_email = settings.DEFAULT_FROM_EMAIL
    connection = get_connection(
        backend=settings.EMAIL_BACKEND,
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=getattr(settings, "EMAIL_USE_TLS", False),
        use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
        timeout=getattr(settings, "EMAIL_TIMEOUT", 15),
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
    Send OTP email.
    Priority: Brevo (Gmail sender, works on Render) -> SMTP -> Resend.
    Returns: {sent, via, error}
    """
    subject, body = _build_otp_message(purpose, otp, extra_context)

    if getattr(settings, "BREVO_API_KEY", "").strip():
        try:
            message_id = _send_via_brevo(email, subject, body)
            result = {"sent": True, "via": "brevo", "error": None}
            if message_id:
                result["email_message_id"] = message_id
            return result
        except Exception as exc:
            logger.error("Brevo failed for %s: %s", email, exc)
            return {"sent": False, "via": "brevo", "error": f"{type(exc).__name__}: {exc}"}

    if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
        if not settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
            try:
                sent = _send_via_smtp(email, subject, body)
                if sent:
                    return {"sent": True, "via": "smtp", "error": None}
                return {"sent": False, "via": "smtp", "error": "SMTP send returned 0"}
            except Exception as exc:
                logger.error("SMTP failed for %s: %s", email, exc)
                return {"sent": False, "via": "smtp", "error": f"{type(exc).__name__}: {exc}"}

    if getattr(settings, "RESEND_API_KEY", "").strip():
        try:
            _send_via_resend(email, subject, body)
            return {"sent": True, "via": "resend", "error": None}
        except Exception as exc:
            logger.error("Resend failed for %s: %s", email, exc)
            return {"sent": False, "via": "resend", "error": f"{type(exc).__name__}: {exc}"}

    return {
        "sent": False,
        "via": "none",
        "error": (
            "No email provider configured. Use Brevo with your Gmail "
            "(brevo.com — verify sender, no domain needed) or set SMTP for local dev."
        ),
    }

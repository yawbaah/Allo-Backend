import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import User
from .utils import get_html_email_template, get_email_copy

logger = logging.getLogger(__name__)


def _send_code_email(user_id: str, code: str, purpose: str):
    """Shared implementation for both email tasks."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[MAIL] User {user_id} not found — skipping email.")
        return {"status": "error", "message": "User not found"}

    subject, title, desc = get_email_copy(purpose)
    html_content = get_html_email_template(title, code, desc)
    plain_content = f"{title}\n\n{desc}\n\nCode: {code}"

    send_mail(
        subject=subject,
        message=plain_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_content,
        fail_silently=False,
    )

    logger.info(f"[MAIL] Sent '{purpose}' email to {user.email}")
    return {"status": "success", "email": user.email}


@shared_task(
    name="accounts.tasks.send_verification_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,          # 10s, 20s, 40s...
    retry_kwargs={"max_retries": 3},
    retry_jitter=True,
)
def send_verification_email(self, user_id: str, code: str):
    return _send_code_email(user_id, code, "verify_email")


@shared_task(
    name="accounts.tasks.send_password_reset_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_kwargs={"max_retries": 3},
    retry_jitter=True,
)
def send_password_reset_email(self, user_id: str, code: str):
    return _send_code_email(user_id, code, "reset_password")
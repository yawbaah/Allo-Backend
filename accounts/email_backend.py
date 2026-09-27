import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class BrevoAPIEmailBackend(BaseEmailBackend):
    """
    Sends mail through Brevo's HTTP API over port 443.
    Required because Railway blocks outbound SMTP (25/465/587).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "BREVO_API_KEY", None)
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 15)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not self.api_key:
            logger.error("[MAIL] BREVO_API_KEY is not set — cannot send email.")
            if not self.fail_silently:
                raise ValueError("BREVO_API_KEY is not configured")
            return 0

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message):
        from_name, from_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)

        payload = {
            "sender": {"email": from_email},
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject,
            "textContent": message.body or " ",
        }

        if from_name:
            payload["sender"]["name"] = from_name

        if message.cc:
            payload["cc"] = [{"email": addr} for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": addr} for addr in message.bcc]
        if message.reply_to:
            _, reply_email = parseaddr(message.reply_to[0])
            payload["replyTo"] = {"email": reply_email}

        # Pull the text/html alternative attached by send_mail(html_message=...)
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["htmlContent"] = content
                break

        try:
            response = requests.post(
                BREVO_ENDPOINT,
                json=payload,
                headers={
                    "api-key": self.api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error(f"[MAIL] Brevo request failed: {e}")
            if not self.fail_silently:
                raise
            return False

        if response.status_code >= 400:
            logger.error(
                f"[MAIL] Brevo rejected the message "
                f"({response.status_code}): {response.text}"
            )
            if not self.fail_silently:
                raise RuntimeError(f"Brevo API error {response.status_code}: {response.text}")
            return False

        logger.info(f"[MAIL] Brevo accepted message for {message.to}")
        return True
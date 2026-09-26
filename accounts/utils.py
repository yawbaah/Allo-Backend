import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailCode

def generate_6digit_code():
    return f"{random.randint(100000, 999999)}"

def get_html_email_template(title, code, description):
    """Generates a premium, dark-mode HTML email matching Allo's brand."""
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #000000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #000000; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background-color: #0a0a0a; border: 1px solid #27272a; border-radius: 8px; overflow: hidden;">
                        <tr>
                            <td style="padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
                                <h1 style="margin: 0; font-size: 28px; font-weight: 600; letter-spacing: -0.05em; color: #ffffff;">Allo</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 30px; text-align: center;">
                                <h2 style="margin: 0 0 15px 0; font-size: 20px; font-weight: 500; color: #ffffff;">{title}</h2>
                                <p style="margin: 0 0 30px 0; font-size: 15px; color: #a1a1aa; line-height: 1.6;">
                                    {description}
                                </p>
                                <div style="background-color: #000000; border: 1px solid #27272a; border-radius: 6px; padding: 20px; margin-bottom: 30px;">
                                    <span style="font-size: 32px; font-weight: 300; letter-spacing: 0.3em; color: #ffffff;">{code}</span>
                                </div>
                                <p style="margin: 0; font-size: 13px; color: #71717a;">
                                    This code expires in 15 minutes. If you didn't request this, please ignore this email.
                                </p>
                            </td>
                        </tr>
                    </table>
                    <p style="margin-top: 30px; font-size: 12px; color: #52525b; text-align: center;">
                        © {timezone.now().year} Allo. All rights reserved.
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

def create_and_send_code(user, purpose):
    EmailCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)

    code_str = generate_6digit_code()
    expires_at = timezone.now() + timedelta(minutes=15)

    EmailCode.objects.create(
        user=user,
        code=code_str,
        purpose=purpose,
        expires_at=expires_at,
    )

    if purpose == 'verify_email':
        subject = "Allo - Verify your email"
        title = "Verify your email address"
        desc = "Welcome to Allo! To complete your setup and access your dashboard, enter the code below."
    else:
        subject = "Allo - Password Reset Code"
        title = "Reset your password"
        desc = "We received a request to reset your password. Enter the code below to choose a new password."

    html_content = get_html_email_template(title, code_str, desc)
    plain_content = f"{title}\n\n{desc}\n\nCode: {code_str}"

    try:
        send_mail(
            subject=subject,
            message=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_content, # <--- This sends the beautiful UI!
        )
    except Exception as e:
        print(f"Error sending email to {user.email}: {e}")

    return code_str
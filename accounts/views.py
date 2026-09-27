import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from companies.models import Company

from .models import EmailCode, User
from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
    VerifyEmailSerializer,
)
from .tasks import send_password_reset_email, send_verification_email
from .utils import issue_code

logger = logging.getLogger(__name__)

VALID_PLANS = ['starter', 'growth', 'business', 'enterprise']


def queue_email(task, user, code):
    """
    Queue a Celery email task. If the broker is unreachable, log it but never
    break the HTTP response.
    """
    try:
        task.delay(str(user.id), code)
    except Exception as e:
        logger.error(f"[MAIL] Could not queue email for {user.email}: {e}")


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data['email'].strip().lower()

        selected_plan = data.get('plan', 'starter')
        if selected_plan not in VALID_PLANS:
            selected_plan = 'starter'

        # 1. Create Company with UNPAID status (locked until payment)
        company = Company.objects.create(
            name=data['company_name'],
            industry=data.get('industry', ''),
            size=data.get('size', ''),
            website_url=data.get('website_url', ''),
            support_email=email,
            notification_email=email,
            plan=selected_plan,
            subscription_status='unpaid',
        )

        # 2. Create User
        user = User.objects.create_user(
            email=email,
            password=data['password'],
            company=company,
            email_verified=False,
        )

        # 3. Create verification code (invalidates any older unused ones)
        code = issue_code(user, 'verify_email')

        # 4. Queue email in background — never blocks the response
        queue_email(send_verification_email, user, code)

        payload = {
            "message": "Company and account created. Verification email sent.",
            "email": user.email,
        }
        if settings.DEBUG:
            payload["dev_code_preview"] = code

        return Response(payload, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email'].strip().lower()
        code_input = serializer.validated_data['code'].strip()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        email_code = EmailCode.objects.filter(
            user=user,
            code=code_input,
            purpose='verify_email',
            used=False,
            expires_at__gt=timezone.now(),
        ).first()

        if not email_code:
            return Response(
                {"error": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_code.used = True
        email_code.save(update_fields=['used'])

        user.email_verified = True
        user.save(update_fields=['email_verified'])

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Email verified successfully.",
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            "user": UserProfileSerializer(user).data,
        }, status=status.HTTP_200_OK)


class ResendVerificationView(APIView):
    """Lets a user request a fresh verification code if the first email failed."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Don't reveal whether the account exists
            return Response(
                {"message": "If that email exists, a new code was sent."},
                status=status.HTTP_200_OK,
            )

        if user.email_verified:
            return Response({"message": "Email is already verified."}, status=status.HTTP_200_OK)

        code = issue_code(user, 'verify_email')
        queue_email(send_verification_email, user, code)

        payload = {"message": "A new verification code was sent."}
        if settings.DEBUG:
            payload["dev_code_preview"] = code

        return Response(payload, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email'].strip().lower()
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "This account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            "user": UserProfileSerializer(user).data,
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email'].strip().lower()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Don't reveal whether the account exists
            return Response(
                {"message": "If that email exists, a code was sent."},
                status=status.HTTP_200_OK,
            )

        code = issue_code(user, 'reset_password')
        queue_email(send_password_reset_email, user, code)

        payload = {"message": "Password reset code sent to email."}
        if settings.DEBUG:
            payload["dev_code_preview"] = code

        return Response(payload, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email'].strip().lower()
        code_input = serializer.validated_data['code'].strip()
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        email_code = EmailCode.objects.filter(
            user=user,
            code=code_input,
            purpose='reset_password',
            used=False,
            expires_at__gt=timezone.now(),
        ).first()

        if not email_code:
            return Response(
                {"error": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_code.used = True
        email_code.save(update_fields=['used'])

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password reset successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)
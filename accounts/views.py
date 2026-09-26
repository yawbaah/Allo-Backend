from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

from .models import User, EmailCode
from companies.models import Company
from .serializers import (
    RegisterSerializer,
    VerifyEmailSerializer,
    LoginSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
)
from .utils import create_and_send_code


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data['email'].strip().lower()
        selected_plan = data.get('plan', 'starter')
        if selected_plan not in ['starter', 'growth', 'business', 'enterprise']:
            selected_plan = 'starter'

        # 1. Create Company with UNPAID status
        company = Company.objects.create(
            name=data['company_name'],
            industry=data.get('industry', ''),
            size=data.get('size', ''),
            website_url=data.get('website_url', ''),
            support_email=email,
            notification_email=email,
            plan=selected_plan,
            subscription_status='unpaid',  # <-- LOCKED UNTIL PAYMENT
        )

        # 2. Create User
        user = User.objects.create_user(
            email=email,
            password=data['password'],
            company=company,
            email_verified=False,
        )

        # 3. Send verification code
        code = create_and_send_code(user, 'verify_email')

        return Response({
            "message": "Company and account created. Verification code sent.",
            "email": user.email,
            "dev_code_preview": code,
        }, status=status.HTTP_201_CREATED)


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
            return Response({"error": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "This account is disabled."}, status=status.HTTP_401_UNAUTHORIZED)

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
            code = create_and_send_code(user, 'reset_password')
            return Response({
                "message": "Password reset code sent to email.",
                "dev_code_preview": code,
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"message": "If that email exists, a code was sent."}, status=status.HTTP_200_OK)


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
            return Response({"error": "Invalid or expired reset code."}, status=status.HTTP_400_BAD_REQUEST)

        email_code.used = True
        email_code.save(update_fields=['used'])

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password reset successfully. You can now log in."}, status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)
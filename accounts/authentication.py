from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model


class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id = validated_token.get('user_id')
        if user_id is None:
            raise InvalidToken('Token contained no user_id claim')

        User = get_user_model()

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found', code='user_not_found')
        except (TypeError, ValueError) as exc:
            raise AuthenticationFailed(
                f'Invalid user id in token (is User.id a UUIDField?): {user_id!r} ({exc})',
                code='bad_user_id',
            )

        if not user.is_active:
            raise AuthenticationFailed('User inactive', code='user_inactive')

        return user
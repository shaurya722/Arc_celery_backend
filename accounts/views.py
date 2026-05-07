from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from datetime import datetime, timezone

from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Create a new user (sign-up). Public."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


class ProfileView(generics.RetrieveUpdateDestroyAPIView):
    """
    Current user profile: GET (read), PUT/PATCH (update), DELETE (deactivate account).
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'message': 'Profile updated successfully.',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


def _blacklist_token(token_str, token_cls):
    """Manually blacklist any JWT token by creating Outstanding + Blacklisted records."""
    token = token_cls(token_str)
    jti = token.payload.get("jti")
    exp = token.payload.get("exp")
    user_id = token.payload.get("user_id")
    user = None
    if user_id:
        try:
            user = get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            pass

    if jti:
        out, _ = OutstandingToken.objects.get_or_create(
            jti=jti,
            defaults={
                "user": user,
                "created_at": datetime.now(timezone.utc),
                "token": token_str,
                "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None,
            },
        )
        BlacklistedToken.objects.get_or_create(token=out)


class LogoutView(APIView):
    """
    Blacklist both the refresh token (body) and the access token (Authorization header).
    Body: ``{"refresh": "<refresh_token>"}``.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            return Response({'detail': 'Field "refresh" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Blacklist refresh token (ignore if already blacklisted or expired)
        try:
            refresh_token = RefreshToken(refresh)
            refresh_token.blacklist()
        except TokenError:
            # Already blacklisted, expired, or otherwise invalid — proceed to blacklist access token
            pass
        except Exception as e:
            return Response({'detail': f'Invalid refresh token: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # Always try to blacklist the access token from the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            access_token_str = auth_header.split(' ', 1)[1]
            try:
                _blacklist_token(access_token_str, AccessToken)
            except Exception as e:
                # Log the error but still return success — the access token will be rejected
                # by BlacklistAwareJWTAuthentication once it expires naturally, and for now
                # we don't want to leak internal errors.
                pass

        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """Request a password reset email (always returns generic message)."""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_active and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            base = getattr(settings, 'FRONTEND_PASSWORD_RESET_BASE', '').rstrip('/')
            if base:
                link = f'{base}?uid={uid}&token={token}'
            else:
                link = (
                    f'Use POST /api/auth/password/reset/confirm/ with '
                    f'uid={uid!r}, token={token!r}, new_password=...'
                )
            subject = getattr(settings, 'PASSWORD_RESET_EMAIL_SUBJECT', 'Password reset')
            body = (
                f'You requested a password reset for {user.get_username()}.\n\n'
                f'{link}\n\n'
                f'If you did not request this, ignore this email.'
            )
            send_mail(
                subject,
                body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'webmaster@localhost',
                [user.email],
                fail_silently=True,
            )
        return Response(
            {'detail': 'If an account exists for this email, password reset instructions were sent.'},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirm reset with uid (base64 user pk), token, and new_password."""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        uid = ser.validated_data['uid']
        token = ser.validated_data['token']
        new_password = ser.validated_data['new_password']
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid uid or user.'}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password has been reset. You can log in with the new password.'})


class LoginView(TokenObtainPairView):
    """Obtain access + refresh JWT (same as ``/api/auth/token/``)."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            data = dict(response.data)
            user = None
            username = request.data.get('username')
            if username:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    user = None
            user_data = UserProfileSerializer(user).data if user else None
            return Response({
                'message': 'Login successful.',
                'access': data.get('access'),
                'refresh': data.get('refresh'),
                'user': user_data,
            }, status=status.HTTP_200_OK)
        return Response({
            'message': 'Invalid credentials.',
            'errors': response.data,
        }, status=response.status_code)


class TokenRefreshPublicView(TokenRefreshView):
    permission_classes = [AllowAny]


class TokenVerifyPublicView(TokenVerifyView):
    permission_classes = [AllowAny]

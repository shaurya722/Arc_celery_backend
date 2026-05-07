from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from django.utils.translation import gettext_lazy as _


class BlacklistAwareJWTAuthentication(JWTAuthentication):
    """
    Extends the default JWTAuthentication to also reject tokens
    that have been explicitly blacklisted (e.g. after logout).
    """

    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)

        jti = validated_token.get("jti")
        if jti and BlacklistedToken.objects.filter(token__jti=jti).exists():
            raise InvalidToken(
                _("Token is blacklisted."), code="token_not_valid"
            )

        return validated_token

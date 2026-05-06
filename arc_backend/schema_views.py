"""OpenAPI schema UI without JWT (browser-friendly)."""

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny


class PublicSpectacularAPIView(SpectacularAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class PublicSpectacularSwaggerView(SpectacularSwaggerView):
    authentication_classes = []
    permission_classes = [AllowAny]


class PublicSpectacularRedocView(SpectacularRedocView):
    authentication_classes = []
    permission_classes = [AllowAny]

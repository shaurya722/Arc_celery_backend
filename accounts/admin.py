from django.contrib import admin
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

# Unregister default admin models so we can override with richer list/search fields
admin.site.unregister(OutstandingToken)
admin.site.unregister(BlacklistedToken)


@admin.register(OutstandingToken)
class OutstandingTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'jti', 'token', 'created_at', 'expires_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'jti', 'token')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user',)


@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'blacklisted_at')
    list_filter = ('blacklisted_at',)
    search_fields = ('token__jti', 'token__token', 'token__user__username', 'token__user__email')
    readonly_fields = ('blacklisted_at',)
    raw_id_fields = ('token',)

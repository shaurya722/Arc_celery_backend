from django.contrib import admin
from .models import Site

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'site_type', 'operator_type', 'is_active', 'community', 'created_at']
    list_filter = ['is_active', 'site_type', 'operator_type', 'community']
    search_fields = ['site_name', 'address_city']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

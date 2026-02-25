from django.contrib import admin
from .models import Community


class CommunityAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'population', 'year', 'is_active', 'start_date', 'end_date']

admin.site.register(Community, CommunityAdmin)

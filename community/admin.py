from django.contrib import admin
from .models import Community, CensusYear, CommunityCensusData


class CommunityAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']


class CensusYearAdmin(admin.ModelAdmin):
    list_display = ['id', 'year', 'created_at']
    search_fields = ['year']
    ordering = ['-year']


class CommunityCensusDataAdmin(admin.ModelAdmin):
    list_display = ['community', 'census_year', 'population', 'tier', 'region', 'is_active', 'start_date', 'end_date']
    list_filter = ['census_year', 'is_active', 'tier', 'region', 'province']
    search_fields = ['community__name']
    filter_horizontal = ['sites']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['community', 'census_year']


admin.site.register(Community, CommunityAdmin)
admin.site.register(CensusYear, CensusYearAdmin)
admin.site.register(CommunityCensusData, CommunityCensusDataAdmin)

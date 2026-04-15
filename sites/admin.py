from django.contrib import admin
from .models import Site, SiteCensusData, SiteReallocation


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['id', 'site_name', 'created_at', 'updated_at']
    search_fields = ['site_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(SiteCensusData)
class SiteCensusDataAdmin(admin.ModelAdmin):
    list_display = ['site', 'census_year', 'community', 'site_type', 'operator_type', 'program_paint', 'program_lights', 'program_solvents', 'program_pesticides', 'is_active', 'region', 'created_at']
    list_filter = ['census_year', 'community', 'is_active', 'site_type', 'operator_type', 'region', 'program_paint', 'program_lights', 'program_solvents', 'program_pesticides']
    search_fields = ['site__site_name', 'address_city']
    ordering = ['-census_year__year', 'site__site_name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['site', 'census_year']


@admin.register(SiteReallocation)
class SiteReallocationAdmin(admin.ModelAdmin):
    list_display = [
        'site_name', 'from_community', 'to_community',
        'census_year', 'reallocated_at', 'created_by'
    ]
    list_filter = ['census_year', 'from_community', 'to_community', 'created_by']
    search_fields = ['site_census_data__site__site_name', 'from_community__name', 'to_community__name', 'reason']
    readonly_fields = ['reallocated_at']
    autocomplete_fields = ['site_census_data', 'from_community', 'to_community', 'census_year', 'created_by']

    def site_name(self, obj):
        return obj.site_census_data.site.site_name

    site_name.short_description = 'Site'

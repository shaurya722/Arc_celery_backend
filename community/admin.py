from django.contrib import admin
from .models import Community, CensusYear, CommunityCensusData, AdjacentCommunity


class CommunityAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'has_boundary', 'created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['adjacent']

    @admin.display(description='Boundary', boolean=True)
    def has_boundary(self, obj):
        return obj.boundary is not None


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


class AdjacentCommunityAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'from_community_name', 'to_communities_names', 'census_year', 'created_at'
    ]
    list_filter = ['census_year']
    search_fields = ['from_community__name', 'census_year__year']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['to_communities']
    autocomplete_fields = ['from_community', 'census_year']

    fieldsets = (
        ('Basic Information', {
            'fields': ('from_community', 'to_communities', 'census_year')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def from_community_name(self, obj):
        return obj.from_community.name
    from_community_name.short_description = 'From Community'

    def to_communities_names(self, obj):
        names = list(obj.to_communities.values_list('name', flat=True))
        return ', '.join(names) if names else 'None'
    to_communities_names.short_description = 'To Communities'


admin.site.register(Community, CommunityAdmin)
admin.site.register(CensusYear, CensusYearAdmin)
admin.site.register(CommunityCensusData, CommunityCensusDataAdmin)
admin.site.register(AdjacentCommunity, AdjacentCommunityAdmin)

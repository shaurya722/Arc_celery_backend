from django.contrib import admin
from .models import Site, SiteCensusData, SiteReallocation


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['id', 'site_name', 'created_at', 'updated_at']
    search_fields = ['site_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


class SiteReallocationInline(admin.TabularInline):
    """Adjacent allocation audit trail for this site census row."""

    model = SiteReallocation
    extra = 0
    can_delete = False
    show_change_link = True
    readonly_fields = [
        'id',
        'from_community',
        'to_community',
        'census_year',
        'program',
        'reallocated_at',
        'created_by',
        'reason',
    ]
    ordering = ['-reallocated_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SiteCensusData)
class SiteCensusDataAdmin(admin.ModelAdmin):
    list_display = [
        'site',
        'census_year',
        'community',
        'site_type',
        'operator_type',
        'program_paint',
        'program_lights',
        'program_solvents',
        'program_pesticides',
        'program_fertilizers',
        'is_active',
        'region',
        'created_at',
    ]
    list_filter = [
        'census_year',
        'community',
        'is_active',
        'site_type',
        'operator_type',
        'region',
        'program_paint',
        'program_lights',
        'program_solvents',
        'program_pesticides',
        'program_fertilizers',
    ]
    search_fields = ['site__site_name', 'address_city', 'community__name']
    ordering = ['-census_year__year', 'site__site_name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['site', 'census_year', 'community']
    inlines = [SiteReallocationInline]


@admin.register(SiteReallocation)
class SiteReallocationAdmin(admin.ModelAdmin):
    list_display = [
        'id_short',
        'site_name',
        'site_census_id',
        'program',
        'from_community',
        'to_community',
        'census_year',
        'reason_short',
        'reallocated_at',
        'created_by',
    ]
    list_filter = ['census_year', 'program', 'from_community', 'to_community', 'created_by']
    search_fields = [
        'id',
        'site_census_data__site__site_name',
        'site_census_data__id',
        'from_community__name',
        'to_community__name',
        'reason',
    ]
    date_hierarchy = 'reallocated_at'
    ordering = ['-reallocated_at']
    readonly_fields = ['id', 'reallocated_at']
    autocomplete_fields = [
        'site_census_data',
        'from_community',
        'to_community',
        'census_year',
        'created_by',
    ]
    fieldsets = (
        (None, {
            'fields': (
                'id',
                'site_census_data',
                'program',
                'from_community',
                'to_community',
                'census_year',
            )
        }),
        ('Details', {
            'fields': ('reason', 'created_by', 'reallocated_at'),
        }),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'site_census_data__site',
                'from_community',
                'to_community',
                'census_year',
                'created_by',
            )
        )

    @admin.display(description='ID')
    def id_short(self, obj):
        s = str(obj.pk)
        return s[:8] + '…' if len(s) > 8 else s

    def site_name(self, obj):
        return obj.site_census_data.site.site_name

    site_name.short_description = 'Site'

    @admin.display(description='Site census')
    def site_census_id(self, obj):
        return obj.site_census_data_id

    @admin.display(description='Reason')
    def reason_short(self, obj):
        if not obj.reason:
            return '—'
        t = obj.reason.strip()
        return t[:60] + '…' if len(t) > 60 else t

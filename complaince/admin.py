from django.contrib import admin
from .models import ComplianceCalculation


@admin.register(ComplianceCalculation)
class ComplianceCalculationAdmin(admin.ModelAdmin):
    list_display = [
        'community',
        'census_year',
        'program',
        'required_sites',
        'actual_sites',
        'shortfall',
        'excess',
        'compliance_rate',
        'calculation_date',
        'created_at'
    ]
    list_filter = ['program','census_year', 'community', 'created_at', 'calculation_date']
    search_fields = ['community__name', 'program', 'census_year__year']
    readonly_fields = ['created_at', 'updated_at', 'calculation_date']
    ordering = ['-calculation_date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'community', 'census_year', 'created_by'
        )

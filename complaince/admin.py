from django.contrib import admin
from .models import ComplianceCalculation


@admin.register(ComplianceCalculation)
class ComplianceCalculationAdmin(admin.ModelAdmin):
    list_display = [
        'community',
        'program',
        'required_sites',
        'actual_sites',
        'shortfall',
        'excess',
        'compliance_rate',
        'created_at'
    ]
    list_filter = ['program', 'community', 'created_at']
    search_fields = ['community__name', 'program']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

from django.contrib import admin
from .models import RegulatoryRule, RegulatoryRuleCensusData


class RegulatoryRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


class RegulatoryRuleCensusDataAdmin(admin.ModelAdmin):
    list_display = ['regulatory_rule', 'census_year', 'program', 'category', 'rule_type', 'is_active', 'start_date', 'end_date']
    list_filter = ['census_year', 'is_active', 'program', 'category', 'rule_type']
    search_fields = ['regulatory_rule__name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['regulatory_rule', 'census_year']


admin.site.register(RegulatoryRule, RegulatoryRuleAdmin)
admin.site.register(RegulatoryRuleCensusData, RegulatoryRuleCensusDataAdmin)
from django.contrib import admin
from .models import RegulatoryRule

# Register your models here.
class RegulatoryRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name','year', 'program', 'category', 'rule_type', 'is_active', 'start_date', 'end_date']

admin.site.register(RegulatoryRule, RegulatoryRuleAdmin)
from django.contrib import admin
from .models import Community, CensusYear, Site

admin.site.register(Community)
admin.site.register(CensusYear)
admin.site.register(Site)
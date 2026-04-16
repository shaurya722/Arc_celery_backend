"""
Community-specific Django signals.

Compliance recalculation when census data changes is handled in
``complaince.signals`` (single place, passes census_year_id to Celery).
"""

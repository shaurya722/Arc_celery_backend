"""
Which communities participate in compliance for a given census year.

Kept in sync between synchronous bulk recalc (API) and ``calculate_all_compliance``.
"""

from community.models import CensusYear, CommunityCensusData
from sites.models import SiteCensusData

from .models import ComplianceCalculation


def community_ids_for_census_year(census_year: CensusYear) -> set:
    """
    Union of communities that should receive ComplianceCalculation rows for ``census_year``:

    - Any CommunityCensusData row for that year (active or inactive; inactive ⇒ zeros from calculator).
    - Any existing ComplianceCalculation for that year (covers orphaned rows after deletes).
    - Any active SiteCensusData with community set for that year.
    - Any SiteReallocation from/to community for that year.

    Returns a set of community UUID primary keys (same type as ``Community.id``).
    """
    # Imported lazily to avoid circular imports with SiteReallocation models layer.
    from sites.models import SiteReallocation

    ids = set(
        CommunityCensusData.objects.filter(census_year=census_year).values_list(
            'community_id', flat=True
        )
    )
    ids |= set(
        ComplianceCalculation.objects.filter(census_year=census_year).values_list(
            'community_id', flat=True
        )
    )
    ids |= set(
        SiteCensusData.objects.filter(census_year=census_year, is_active=True)
        .exclude(community__isnull=True)
        .values_list('community_id', flat=True)
    )
    ids |= set(
        SiteReallocation.objects.filter(census_year=census_year).values_list(
            'from_community_id', flat=True
        )
    )
    ids |= set(
        SiteReallocation.objects.filter(census_year=census_year).values_list(
            'to_community_id', flat=True
        )
    )
    return {i for i in ids if i is not None}


def communities_queryset_for_census_year(census_year: CensusYear):
    """``Community`` queryset ordered by name for compliance bulk jobs."""
    from community.models import Community

    ids = community_ids_for_census_year(census_year)
    return Community.objects.filter(id__in=ids).order_by('name')

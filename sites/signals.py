"""
Site-related Django signals.

Compliance recalculation for ``SiteCensusData`` is handled in
``complaince.signals`` (avoids duplicate Celery jobs and wrong task args).

Do not use ``Site.community_id`` — ``Site`` has no community FK; community
lives on ``SiteCensusData``.
"""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import SiteCensusData, SiteReallocation


@receiver(post_delete, sender=SiteReallocation)
def sync_site_community_after_reallocation_delete(sender, instance, **kwargs):
    """
    If a SiteReallocation row is removed (admin delete, raw SQL, etc.), refresh
    compliance for the affected communities and program. The site's
    ``community`` FK is NOT touched: per-program reallocation never moved it.
    """
    try:
        sc = SiteCensusData.objects.get(pk=instance.site_census_data_id)
    except SiteCensusData.DoesNotExist:
        return

    _refresh_compliance_after_reallocation_change(
        sc,
        instance.from_community_id,
        instance.to_community_id,
        program=instance.program,
    )


def _refresh_compliance_after_reallocation_change(
    site_census_data, from_community_id, to_community_id, program=None
):
    """Persist ComplianceCalculation for communities affected by a reallocation change.

    When ``program`` is provided (per-program SiteReallocation row) we only
    recompute that program. For legacy NULL-program rows we fall back to
    recomputing every program the site participates in.
    """
    from community.models import Community
    from complaince.models import ComplianceCalculation
    from complaince.utils import calculate_compliance
    from sites.adjacent_reallocation import PROGRAM_FIELD

    cy = site_census_data.census_year
    if program:
        programs = [program]
    else:
        programs = [p for p, f in PROGRAM_FIELD.items() if getattr(site_census_data, f, False)]
        if not programs:
            programs = list(PROGRAM_FIELD.keys())

    for cid in {from_community_id, to_community_id}:
        if not cid:
            continue
        try:
            community = Community.objects.get(pk=cid)
        except Community.DoesNotExist:
            continue
        for prog in programs:
            metrics = calculate_compliance(community, prog, cy)
            ComplianceCalculation.objects.update_or_create(
                community=community,
                program=prog,
                census_year=cy,
                defaults={
                    'required_sites': metrics['required_sites'],
                    'actual_sites': metrics['actual_sites'],
                    'shortfall': metrics['shortfall'],
                    'excess': metrics['excess'],
                    'compliance_rate': metrics['compliance_rate'],
                    'created_by': None,
                },
            )

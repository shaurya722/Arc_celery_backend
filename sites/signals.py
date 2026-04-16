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
    If a SiteReallocation row is removed (admin delete, raw SQL, etc.), move
    SiteCensusData.community back to the logical home so inbound caps and listings
    stay consistent. Matches SiteReallocationService.undo_reallocation behaviour.
    """
    try:
        sc = SiteCensusData.objects.get(pk=instance.site_census_data_id)
    except SiteCensusData.DoesNotExist:
        return

    prev = sc.reallocations.order_by('-reallocated_at').first()
    revert_to = prev.to_community if prev else instance.from_community
    if sc.community_id != revert_to.id:
        sc.community = revert_to
        sc.save(update_fields=['community'])

    _refresh_compliance_after_reallocation_change(sc, instance.from_community_id, instance.to_community_id)


def _refresh_compliance_after_reallocation_change(site_census_data, from_community_id, to_community_id):
    """Persist ComplianceCalculation for communities affected by a reallocation change."""
    from community.models import Community
    from complaince.models import ComplianceCalculation
    from complaince.utils import calculate_compliance
    from sites.adjacent_reallocation import PROGRAM_FIELD

    cy = site_census_data.census_year
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
        for program in programs:
            metrics = calculate_compliance(community, program, cy)
            ComplianceCalculation.objects.update_or_create(
                community=community,
                program=program,
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

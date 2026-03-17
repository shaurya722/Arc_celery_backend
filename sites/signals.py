from typing import Optional

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Site, SiteCensusData


def _trigger_recalculation(community_id: Optional[str], program: str = None, census_year_id: Optional[str] = None):
    if not community_id:
        return

    from complaince.tasks import calculate_community_compliance

    if program and census_year_id:
        calculate_community_compliance.delay(str(community_id), program, str(census_year_id))
    else:
        # If no specific program/year, trigger for all programs and latest year
        # But for now, since it's not specific, perhaps skip or trigger for common programs
        pass


# @receiver(pre_save, sender=Site)
# def store_previous_state(sender, instance, **kwargs):
#     """Capture the previous community id and is_active for comparison after save."""
#     if not instance.pk:
#         instance._old_community_id = None
#         instance._old_is_active = None
#         return

#     try:
#         old_instance = Site.objects.get(pk=instance.pk)
#         instance._old_community_id = old_instance.community_id
#         instance._old_is_active = old_instance.is_active
#     except Site.DoesNotExist:
#         instance._old_community_id = None
#         instance._old_is_active = None


# @receiver(post_save, sender=Site)
# def trigger_compliance_on_save(sender, instance, created, **kwargs):
#     """Recalculate compliance when a site is created or updated."""
#     community_ids = set()

#     old_community_id = getattr(instance, "_old_community_id", None)
#     old_is_active = getattr(instance, "_old_is_active", None)

#     # Trigger if community changed
#     if old_community_id:
#         community_ids.add(old_community_id)
#     if instance.community_id:
#         community_ids.add(instance.community_id)

#     # Trigger if is_active changed and site has community
#     if old_is_active is not None and old_is_active != instance.is_active and instance.community_id:
#         community_ids.add(instance.community_id)

#     for community_id in community_ids:
#         _trigger_recalculation(community_id)


@receiver(post_delete, sender=Site)
def trigger_compliance_on_delete(sender, instance, **kwargs):
    """Recalculate compliance when a site is deleted."""
    if instance.community_id:
        _trigger_recalculation(instance.community_id)


@receiver(post_save, sender=SiteCensusData)
@receiver(post_delete, sender=SiteCensusData)
def recalculate_compliance_on_site_census_change(sender, instance, **kwargs):
    """
    Recalculate compliance for the community and census year when site census data changes.
    Triggers calculation for each program the site participates in.
    """
    community = instance.community
    census_year = instance.census_year
    
    if not community or not census_year:
        return
    
    # Map program fields to program names (capitalize first letter to match compliance)
    program_map = {
        'program_paint': 'Paint',
        'program_lights': 'Lighting',
        'program_solvents': 'Solvents',
        'program_pesticides': 'Pesticides',
        'program_fertilizers': 'Fertilizers'
    }
    
    for program_field, program_name in program_map.items():
        if getattr(instance, program_field, False):
            _trigger_recalculation(str(community.id), program_name, str(census_year.id))

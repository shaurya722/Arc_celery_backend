from typing import Optional

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Community


def _trigger_recalculation(community_id: Optional[str]):
    if not community_id:
        return

    from complaince.tasks import calculate_community_compliance

    calculate_community_compliance(str(community_id))


@receiver(pre_save, sender=Community)
def store_previous_state(sender, instance, **kwargs):
    """Capture the previous is_active for comparison after save."""
    if not instance.pk:
        instance._old_is_active = None
        return

    try:
        old_instance = Community.objects.get(pk=instance.pk)
        instance._old_is_active = old_instance.is_active
    except Community.DoesNotExist:
        instance._old_is_active = None


@receiver(post_save, sender=Community)
def trigger_compliance_on_save(sender, instance, created, **kwargs):
    """Recalculate compliance when community is_active changes."""
    old_is_active = getattr(instance, "_old_is_active", None)

    if old_is_active is not None and old_is_active != instance.is_active:
        _trigger_recalculation(instance.id)

"""
Community-specific Django signals.

Compliance recalculation when census data changes is handled in
``complaince.signals`` (single place, passes census_year_id to Celery).

Also auto-populates Community.adjacent on create/update when a boundary is present,
using shapely to detect touching/intersecting neighbors. If shapely is unavailable,
the signal skips gracefully.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Community

logger = logging.getLogger(__name__)

try:  # Optional dependency
    from shapely.geometry import shape
except Exception:  # pragma: no cover
    shape = None


def _compute_neighbors_for(community: Community):
    """Recompute adjacency for a single community based on its boundary."""
    if shape is None:
        logger.info("Shapely not installed; skipping auto-adjacency for communities")
        return
    if not community.boundary:
        return
    try:
        g1 = shape(community.boundary)
    except Exception as e:
        logger.warning(f"Invalid geometry for community {community.id}: {e}")
        return

    # Find candidate neighbors: those with a boundary and not self
    candidates = Community.objects.exclude(id=community.id).exclude(boundary__isnull=True).only("id", "boundary")

    # Clear existing links and rebuild for this node
    community.adjacent.clear()
    to_add = []

    for other in candidates.iterator():
        try:
            g2 = shape(other.boundary)
            if g1.touches(g2) or g1.intersects(g2):
                to_add.append(other)
        except Exception:
            continue

    if to_add:
        community.adjacent.add(*to_add)


@receiver(post_save, sender=Community)
def populate_adjacency_on_save(sender, instance: Community, created, **kwargs):
    """
    When a Community is created or its boundary is updated, recompute its adjacency.
    Skips if no boundary is present or shapely is unavailable.
    """
    # Allow bulk operations to disable adjacency recomputation
    if getattr(settings, "COMMUNITY_SKIP_ADJACENCY", False):
        return
    # Only act if a boundary exists
    if not instance.boundary:
        return

    # If update_fields present and boundary not updated, skip heavy work
    update_fields = kwargs.get("update_fields")
    if (not created) and update_fields and ("boundary" not in update_fields):
        return

    _compute_neighbors_for(instance)

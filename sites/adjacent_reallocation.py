"""
Adjacent site reallocation rules (Tool C): map ``Community.adjacent`` when set, else legacy
``AdjacentCommunity``; regulatory cap; excess/shortfall.

See ss.md §5. Cap: reallocation_percentage from RegulatoryRuleCensusData (rule_type=Reallocation)
per program + census year, default 35% of target community required sites (ceil so small
required counts are not capped to zero, e.g. 35% of 1 required → 1 inbound slot).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from django.db.models import Count, Q

from community.models import AdjacentCommunity, CensusYear, Community, CommunityCensusData
from regulatory_rules.models import RegulatoryRuleCensusData
from sites.models import SiteReallocation

PROGRAM_FIELD = {
    'Paint': 'program_paint',
    'Lighting': 'program_lights',
    'Solvents': 'program_solvents',
    'Pesticides': 'program_pesticides',
    'Fertilizers': 'program_fertilizers',
}

# Last-resort fallback when *no* active Reallocation rule provides a percentage.
# Prefer pulling a percentage from RegulatoryRuleCensusData whenever possible.
FALLBACK_REALLOCATION_PERCENT = 10

# Alias for callers that expect this name (same value as ``FALLBACK_REALLOCATION_PERCENT``).
DEFAULT_REALLOCATION_PERCENT = FALLBACK_REALLOCATION_PERCENT

HSP_PROGRAMS = {"Paint", "Solvents", "Pesticides", "Fertilizers"}


def infer_program_from_site(site_census_data) -> Optional[str]:
    for prog, field in PROGRAM_FIELD.items():
        if getattr(site_census_data, field, False):
            return prog
    return None


def get_reallocation_percentage_cap(census_year: CensusYear, program: str) -> int:
    """
    Active regulatory Reallocation rule percentage.

    Preference order:
    1) program-specific Reallocation rule (same census year)
    2) any active Reallocation rule for the census year (used as a global default)
    3) FALLBACK_REALLOCATION_PERCENT
    """
    rule = (
        RegulatoryRuleCensusData.objects.filter(
            census_year=census_year,
            program=program,
            rule_type='Reallocation',
            is_active=True,
        )
        .exclude(reallocation_percentage__isnull=True)
        .order_by('-updated_at')
        .first()
    )
    if rule and rule.reallocation_percentage is not None:
        return max(0, min(100, int(rule.reallocation_percentage)))

    global_rule = (
        RegulatoryRuleCensusData.objects.filter(
            census_year=census_year,
            rule_type='Reallocation',
            is_active=True,
        )
        .exclude(reallocation_percentage__isnull=True)
        .order_by('-updated_at')
        .first()
    )
    if global_rule and global_rule.reallocation_percentage is not None:
        return max(0, min(100, int(global_rule.reallocation_percentage)))

    return FALLBACK_REALLOCATION_PERCENT


def is_adjacent_for_reallocation(
    from_community: Community,
    to_community: Community,
    census_year: CensusYear,
    program: Optional[str] = None,
) -> bool:
    """
    True if to_community may receive reallocations from from_community for a program.

    When ``Community.adjacent`` (map neighbors) has any rows for ``from_community``, only those
    M2M edges count — same as ``adjacent_ids`` on map APIs. Legacy ``AdjacentCommunity`` and
    same-region shortcuts apply only if the map has no neighbors for that community.
    """
    if from_community.pk == to_community.pk:
        return False

    if from_community.adjacent.exists():
        return from_community.adjacent.filter(pk=to_community.pk).exists()

    if program in HSP_PROGRAMS:
        try:
            from_cd = CommunityCensusData.objects.get(community=from_community, census_year=census_year)
            to_cd = CommunityCensusData.objects.get(community=to_community, census_year=census_year)
            if from_cd.region and to_cd.region and from_cd.region == to_cd.region:
                return True
        except CommunityCensusData.DoesNotExist:
            pass

    try:
        ac = AdjacentCommunity.objects.get(from_community=from_community, census_year=census_year)
        if ac.to_communities.filter(pk=to_community.pk).exists():
            return True
    except AdjacentCommunity.DoesNotExist:
        pass

    try:
        ac_rev = AdjacentCommunity.objects.get(from_community=to_community, census_year=census_year)
        if ac_rev.to_communities.filter(pk=from_community.pk).exists():
            return True
    except AdjacentCommunity.DoesNotExist:
        pass

    return False


def count_inbound_reallocations_for_program(
    to_community: Community,
    census_year: CensusYear,
    program: str,
) -> int:
    field = PROGRAM_FIELD.get(program)
    if not field:
        return 0
    # Per-program rows have ``program`` set; legacy NULL rows are matched by the
    # site's program flag for backwards compatibility.
    return SiteReallocation.objects.filter(
        to_community=to_community,
        census_year=census_year,
    ).filter(
        Q(program=program)
        | Q(program__isnull=True, **{f'site_census_data__{field}': True})
    ).count()


def max_inbound_reallocations_allowed(
    to_community: Community,
    census_year: CensusYear,
    program: str,
    required_sites: int,
) -> int:
    pct = get_reallocation_percentage_cap(census_year, program)
    return max_inbound_reallocations_allowed_with_pct(required_sites, pct)


def max_inbound_reallocations_allowed_with_pct(required_sites: int, pct: int) -> int:
    if required_sites <= 0 or pct <= 0:
        return 0
    return int(math.ceil(required_sites * (pct / 100.0)))


def inbound_reallocation_counts_by_community(
    census_year: CensusYear, program: str
) -> Dict[int, int]:
    """Single grouped query: to_community_id -> count of inbound reallocations for program."""
    field = PROGRAM_FIELD.get(program)
    if not field:
        return {}
    rows = (
        SiteReallocation.objects.filter(census_year=census_year)
        .filter(
            Q(program=program)
            | Q(program__isnull=True, **{f'site_census_data__{field}': True})
        )
        .values('to_community_id')
        .annotate(c=Count('id'))
    )
    return {int(r['to_community_id']): int(r['c']) for r in rows}


def reallocation_cap_status_dict(
    required_sites: int,
    regulatory_pct: int,
    inbound_used: int,
) -> dict:
    max_allowed = max_inbound_reallocations_allowed_with_pct(required_sites, regulatory_pct)
    return {
        'regulatory_reallocation_percentage': regulatory_pct,
        'required_sites': required_sites,
        'max_inbound_reallocations': max_allowed,
        'inbound_reallocations_used': inbound_used,
        'inbound_reallocations_remaining': max(0, max_allowed - inbound_used),
    }


def reallocation_cap_status(
    to_community: Community,
    census_year: CensusYear,
    program: str,
    required_sites: int,
) -> dict:
    pct = get_reallocation_percentage_cap(census_year, program)
    used = count_inbound_reallocations_for_program(to_community, census_year, program)
    return reallocation_cap_status_dict(required_sites, pct, used)


def neighbors_for_reallocation(source: Community, census_year: CensusYear) -> list:
    """
    Neighbors for Tool C listings: map ``Community.adjacent`` only when that M2M is non-empty
    (matches map ``adjacent_ids``). Otherwise legacy ``AdjacentCommunity`` (both directions).
    """
    mapped = list(source.adjacent.all().order_by('name'))
    if mapped:
        return mapped

    seen = set()
    ordered = []

    try:
        ac = AdjacentCommunity.objects.prefetch_related('to_communities').get(
            from_community=source, census_year=census_year
        )
        for c in ac.to_communities.all():
            if c.pk not in seen:
                seen.add(c.pk)
                ordered.append(c)
    except AdjacentCommunity.DoesNotExist:
        pass

    for ac in AdjacentCommunity.objects.filter(
        census_year=census_year, to_communities=source
    ).select_related('from_community'):
        c = ac.from_community
        if c.pk not in seen:
            seen.add(c.pk)
            ordered.append(c)

    return ordered

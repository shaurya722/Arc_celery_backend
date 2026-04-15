"""
Adjacent site reallocation rules (Tool C): map + legacy adjacency, regulatory cap, excess/shortfall.

See ss.md §5. Cap: reallocation_percentage from RegulatoryRuleCensusData (rule_type=Reallocation)
per program + census year, default 35% of target community required sites (floor).
"""
from __future__ import annotations

import math
from typing import Optional

from community.models import AdjacentCommunity, CensusYear, Community
from regulatory_rules.models import RegulatoryRuleCensusData
from sites.models import SiteReallocation

PROGRAM_FIELD = {
    'Paint': 'program_paint',
    'Lighting': 'program_lights',
    'Solvents': 'program_solvents',
    'Pesticides': 'program_pesticides',
    'Fertilizers': 'program_fertilizers',
}

# When no active Reallocation rule defines a percentage (ss.md uses 35% for event-style caps;
# product asks for 35% of required sites toward adjacent allocation).
DEFAULT_REALLOCATION_PERCENT = 35


def infer_program_from_site(site_census_data) -> Optional[str]:
    for prog, field in PROGRAM_FIELD.items():
        if getattr(site_census_data, field, False):
            return prog
    return None


def get_reallocation_percentage_cap(census_year: CensusYear, program: str) -> int:
    """Active regulatory Reallocation rule percentage, or DEFAULT_REALLOCATION_PERCENT."""
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
    return DEFAULT_REALLOCATION_PERCENT


def is_adjacent_for_reallocation(
    from_community: Community,
    to_community: Community,
    census_year: CensusYear,
) -> bool:
    """
    True if to_community may receive reallocations from from_community:
    - Map-drawn symmetrical adjacency (Community.adjacent), or
    - Legacy AdjacentCommunity in either direction for this census year.
    """
    if from_community.pk == to_community.pk:
        return False

    if from_community.adjacent.filter(pk=to_community.pk).exists():
        return True

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
    return SiteReallocation.objects.filter(
        to_community=to_community,
        census_year=census_year,
        **{f'site_census_data__{field}': True},
    ).count()


def max_inbound_reallocations_allowed(
    to_community: Community,
    census_year: CensusYear,
    program: str,
    required_sites: int,
) -> int:
    pct = get_reallocation_percentage_cap(census_year, program)
    if required_sites <= 0:
        return 0
    return int(math.floor(required_sites * (pct / 100.0)))


def reallocation_cap_status(
    to_community: Community,
    census_year: CensusYear,
    program: str,
    required_sites: int,
) -> dict:
    pct = get_reallocation_percentage_cap(census_year, program)
    max_allowed = max_inbound_reallocations_allowed(
        to_community, census_year, program, required_sites
    )
    used = count_inbound_reallocations_for_program(to_community, census_year, program)
    return {
        'regulatory_reallocation_percentage': pct,
        'required_sites': required_sites,
        'max_inbound_reallocations': max_allowed,
        'inbound_reallocations_used': used,
        'inbound_reallocations_remaining': max(0, max_allowed - used),
    }


def neighbors_for_reallocation(source: Community, census_year: CensusYear) -> list:
    """
    Unique adjacent communities: map-drawn (Community.adjacent) plus legacy AdjacentCommunity
    (both directions) for this census year.
    """
    seen = set()
    ordered = []

    for c in source.adjacent.all().order_by('name'):
        if c.pk not in seen:
            seen.add(c.pk)
            ordered.append(c)

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

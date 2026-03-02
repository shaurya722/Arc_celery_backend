"""
Compliance calculation utilities.
"""
import math
from typing import Dict, Optional
from django.db.models import Q
from regulatory_rules.models import RegulatoryRule, RegulatoryRuleCensusData
from community.models import Community, CommunityCensusData, CensusYear
from sites.models import Site, SiteCensusData


def calculate_required_sites_from_rule(
    community: Community,
    program: str,
    census_year: Optional[CensusYear] = None
) -> Optional[int]:
    """
    Calculate required sites based on RegulatoryRuleCensusData.
    
    Args:
        community: Community instance
        program: Program name (Paint, Lighting, Solvents, Pesticides)
        census_year: CensusYear instance (defaults to latest census year for community)
    
    Returns:
        Number of required sites or None if no rule found
    """
    if census_year is None:
        # Get the latest census year for this community
        latest_census_data = community.census_data.order_by('-census_year__year').first()
        if latest_census_data:
            census_year = latest_census_data.census_year
        else:
            return None  # No census data for this community
    
    # Get community census data for this year
    try:
        community_census = CommunityCensusData.objects.get(
            community=community,
            census_year=census_year
        )
        population = community_census.population
    except CommunityCensusData.DoesNotExist:
        return None
    
    # Query for active Site Requirements rules matching program and census year
    rule_census_data = RegulatoryRuleCensusData.objects.filter(
        program=program,
        census_year=census_year,
        rule_type='Site Requirements',
        is_active=True
    ).filter(
        Q(min_population__lte=population) | Q(min_population__isnull=True),
        Q(max_population__gte=population) | Q(max_population__isnull=True)
    ).select_related('regulatory_rule').order_by('min_population')
    
    for rule_data in rule_census_data:
        # Check if population falls within rule's range
        if rule_data.min_population is not None and population < rule_data.min_population:
            continue
        if rule_data.max_population is not None and population > rule_data.max_population:
            continue
        
        # Calculate based on rule
        # Formula: required_sites = ceil(population / site_per_population) * base_required_sites
        if rule_data.site_per_population is not None and rule_data.base_required_sites is not None:
            # Both values present: multiply them
            value_a = math.ceil(population / rule_data.site_per_population)
            required = value_a * rule_data.base_required_sites
        elif rule_data.base_required_sites is not None:
            # Only base requirement (flat requirement)
            required = rule_data.base_required_sites
        elif rule_data.site_per_population is not None:
            # Only population divisor
            required = math.ceil(population / rule_data.site_per_population)
        else:
            continue
        
        return required
    
    return None


def calculate_required_sites_fallback(population: int, program: str) -> int:
    """
    Fallback calculation based on standard formulas when no RegulatoryRule exists.
    
    Args:
        population: Community population
        program: Program name
    
    Returns:
        Number of required sites
    """
    if program == "Paint":
        if population < 1000:
            return 0
        elif population < 5000:
            return 1
        elif population <= 500000:
            return math.ceil(population / 40000)
        else:
            return 13 + math.ceil((population - 500000) / 150000)
    
    elif program == "Lighting":
        if population < 1000:
            return 0
        elif population <= 500000:
            return math.ceil(population / 15000)
        else:
            return 34 + math.ceil((population - 500000) / 50000)
    
    elif program in ["Solvents", "Pesticides"]:
        if population < 1000:
            return 0
        elif population < 10000:
            return 1
        elif population <= 500000:
            return math.ceil(population / 250000)
        else:
            return 2 + math.ceil((population - 500000) / 300000)
    
    return 0


def calculate_required_sites(
    community: Community,
    program: str,
    census_year: Optional[CensusYear] = None
) -> int:
    """
    Calculate required sites with RegulatoryRuleCensusData priority and fallback.
    
    Args:
        community: Community instance
        program: Program name
        census_year: CensusYear instance (defaults to latest census year for community)
    
    Returns:
        Number of required sites
    """
    # Try RegulatoryRuleCensusData first
    required = calculate_required_sites_from_rule(community, program, census_year)
    
    # Fallback to standard calculation
    if required is None:
        # Get population from census data
        if census_year is None:
            latest_census_data = community.census_data.order_by('-census_year__year').first()
            if latest_census_data:
                population = latest_census_data.population
            else:
                return 0
        else:
            try:
                community_census = CommunityCensusData.objects.get(
                    community=community,
                    census_year=census_year
                )
                population = community_census.population
            except CommunityCensusData.DoesNotExist:
                return 0
        
        required = calculate_required_sites_fallback(population, program)
    
    return required


def count_actual_sites(community: Community, program: str, census_year: Optional[CensusYear] = None) -> int:
    """
    Count actual active sites for a community and program in a specific census year.
    
    Args:
        community: Community instance
        program: Program name (Paint, Lighting, Solvents, Pesticides, Fertilizers)
        census_year: CensusYear instance (defaults to latest census year for community)
    
    Returns:
        Number of active sites
    """
    program_field_map = {
        'Paint': 'program_paint',
        'Lighting': 'program_lights',
        'Solvents': 'program_solvents',
        'Pesticides': 'program_pesticides',
        'Fertilizers': 'program_fertilizers',
    }
    
    program_field = program_field_map.get(program)
    if not program_field:
        return 0
    
    if census_year is None:
        # Get the latest census year for this community
        latest_census_data = community.census_data.order_by('-census_year__year').first()
        if latest_census_data:
            census_year = latest_census_data.census_year
        else:
            return 0
    
    # Count active sites with the program enabled that are associated with this community in this census year
    filter_kwargs = {
        'community': community,
        'census_year': census_year,
        'is_active': True,
        program_field: True
    }
    
    return SiteCensusData.objects.filter(**filter_kwargs).count()


def calculate_compliance(
    community: Community,
    program: str,
    census_year: Optional[CensusYear] = None
) -> Dict:
    """
    Calculate compliance metrics for a community and program in a specific census year.
    Uses is_active status from Community Census Data, Regulatory Rule Census Data, and Site Census Data.
    
    Returns zero metrics when community is inactive or no active rules exist (instead of None).
    
    Args:
        community: Community instance
        program: Program name
        census_year: CensusYear instance (defaults to latest census year for community)
    
    Returns:
        Dictionary with compliance metrics (returns zeros if inactive):
        - required_sites: int
        - actual_sites: int
        - shortfall: int (0 if compliant)
        - excess: int (0 if not compliant)
        - compliance_rate: float (percentage)
    """
    # Zero metrics to return when inactive
    zero_metrics = {
        'required_sites': 0,
        'actual_sites': 0,
        'shortfall': 0,
        'excess': 0,
        'compliance_rate': 0.0
    }
    
    # Get census year if not provided
    if census_year is None:
        latest_census_data = community.census_data.order_by('-census_year__year').first()
        if latest_census_data:
            census_year = latest_census_data.census_year
        else:
            return zero_metrics  # No census data - return zeros
    
    # Check if community is active in this census year (Community Census Data is_active)
    try:
        community_census = CommunityCensusData.objects.get(
            community=community,
            census_year=census_year
        )
        if not community_census.is_active:
            # Community not active - return zero metrics
            return zero_metrics
    except CommunityCensusData.DoesNotExist:
        # No census data for community - return zero metrics
        return zero_metrics
    
    # Check if there are any active regulatory rules for this program in this census year
    active_rules_exist = RegulatoryRuleCensusData.objects.filter(
        program=program,
        census_year=census_year,
        is_active=True
    ).exists()
    
    if not active_rules_exist:
        # No active regulatory rules for this program - return zero metrics
        return zero_metrics
    
    # Calculate required sites (uses active Regulatory Rule Census Data)
    required_sites = calculate_required_sites(community, program, census_year)
    
    # Count actual sites (uses active Site Census Data)
    actual_sites = count_actual_sites(community, program, census_year)
    
    shortfall = max(0, required_sites - actual_sites)
    excess = max(0, actual_sites - required_sites)
    
    if required_sites > 0:
        compliance_rate = min(100.0, (actual_sites / required_sites) * 100)
    else:
        compliance_rate = 100.0 if actual_sites == 0 else 100.0
    
    return {
        'required_sites': required_sites,
        'actual_sites': actual_sites,
        'shortfall': shortfall,
        'excess': excess,
        'compliance_rate': round(compliance_rate, 2)
    }

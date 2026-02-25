"""
Compliance calculation utilities.
"""
import math
from typing import Dict, Optional
from django.db.models import Q
from regulatory_rules.models import RegulatoryRule
from community.models import Community
from sites.models import Site


def calculate_required_sites_from_rule(
    community: Community,
    program: str,
    year: Optional[int] = None
) -> Optional[int]:
    """
    Calculate required sites based on RegulatoryRule.
    
    Args:
        community: Community instance
        program: Program name (Paint, Lighting, Solvents, Pesticides)
        year: Year for the rule (defaults to community.year)
    
    Returns:
        Number of required sites or None if no rule found
    """
    if year is None:
        year = community.year
    
    population = community.population
    
    # Query for active Site Requirements rules matching program, year, and category
    rules = RegulatoryRule.objects.filter(
        program=program,
        year=year,
        rule_type='Site Requirements',
        is_active=True
    ).filter(
        Q(min_population__lte=population) | Q(min_population__isnull=True),
        Q(max_population__gte=population) | Q(max_population__isnull=True)
    ).order_by('min_population')
    
    for rule in rules:
        # Check if population falls within rule's range
        if rule.min_population is not None and population < rule.min_population:
            continue
        if rule.max_population is not None and population > rule.max_population:
            continue
        
        # Calculate based on rule
        if rule.base_required_sites is not None:
            # Flat base requirement
            required = rule.base_required_sites
        elif rule.site_per_population is not None:
            # Calculate based on population divisor
            required = math.ceil(population / rule.site_per_population)
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
    year: Optional[int] = None
) -> int:
    """
    Calculate required sites with RegulatoryRule priority and fallback.
    
    Args:
        community: Community instance
        program: Program name
        year: Year for the rule (defaults to community.year)
    
    Returns:
        Number of required sites
    """
    # Try RegulatoryRule first
    required = calculate_required_sites_from_rule(community, program, year)
    
    # Fallback to standard calculation
    if required is None:
        required = calculate_required_sites_fallback(community.population, program)
    
    return required


def count_actual_sites(community: Community, program: str) -> int:
    """
    Count actual active sites for a community and program.
    
    Args:
        community: Community instance
        program: Program name (Paint, Lighting, Solvents, Pesticides, Fertilizers)
    
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
    
    # Count active sites with the program enabled
    filter_kwargs = {
        'community': community,
        'is_active': True,
        program_field: True
    }
    
    return Site.objects.filter(**filter_kwargs).count()


def calculate_compliance(
    community: Community,
    program: str,
    year: Optional[int] = None
) -> Dict:
    """
    Calculate compliance metrics for a community and program.
    
    Args:
        community: Community instance
        program: Program name
        year: Year for the rule (defaults to community.year)
    
    Returns:
        Dictionary with compliance metrics:
        - required_sites: int
        - actual_sites: int
        - shortfall: int (0 if compliant)
        - excess: int (0 if not compliant)
        - compliance_rate: float (percentage)
    """
    if not community.is_active:
        return {
            'required_sites': 0,
            'actual_sites': 0,
            'shortfall': 0,
            'excess': 0,
            'compliance_rate': 0.0
        }
    
    required_sites = calculate_required_sites(community, program, year)
    actual_sites = count_actual_sites(community, program)
    
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

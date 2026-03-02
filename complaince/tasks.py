"""
Celery tasks for compliance calculations.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from community.models import Community, CommunityCensusData, CensusYear
from complaince.models import ComplianceCalculation
from complaince.utils import calculate_compliance

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def calculate_all_compliance(self, census_year_id: int = None):
    """
    Calculate compliance for all active communities and programs in a specific census year.
    Runs periodically to update compliance metrics.
    
    Args:
        census_year_id: Optional census year ID. If None, uses the latest census year.
    """
    try:
        now = timezone.now()
        local_now = timezone.localtime(now)
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        programs = ['Paint', 'Lighting', 'Solvents', 'Pesticides']
        
        # Get census year
        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=census_year_id)
            except CensusYear.DoesNotExist:
                logger.error(f"Census year with id {census_year_id} not found")
                return
        else:
            # Get the latest census year
            census_year = CensusYear.objects.order_by('-year').first()
            if not census_year:
                logger.error("No census year found")
                return
        
        # Get all active communities in this census year
        active_census_data = CommunityCensusData.objects.filter(
            census_year=census_year,
            is_active=True
        ).select_related('community')
        
        total_calculations = 0
        total_communities = active_census_data.count()
        
        logger.info(f"Starting compliance calculations for {total_communities} communities in year {census_year.year} at {now_str}")
        
        with transaction.atomic():
            for census_data in active_census_data:
                community = census_data.community
                for program in programs:
                    # Calculate compliance metrics (returns zeros if inactive)
                    metrics = calculate_compliance(community, program, census_year)
                    
                    # Create or update compliance calculation record (even with zero values)
                    ComplianceCalculation.objects.update_or_create(
                        community=community,
                        program=program,
                        census_year=census_year,
                        defaults={
                            'required_sites': metrics['required_sites'],
                            'actual_sites': metrics['actual_sites'],
                            'shortfall': metrics['shortfall'],
                            'excess': metrics['excess'],
                            'compliance_rate': metrics['compliance_rate'],
                            'created_by': None
                        }
                    )
                    
                    total_calculations += 1
                    
                    # Log inactive or zero compliance
                    if all(v == 0 for v in [metrics['required_sites'], metrics['actual_sites'], metrics['compliance_rate']]):
                        logger.info(
                            f"Zero compliance: {community.name} - {program} (Year: {census_year.year}) "
                            f"(inactive community or no active rules)"
                        )
                    # Log non-compliant communities
                    elif metrics['shortfall'] > 0:
                        logger.warning(
                            f"Non-compliant: {community.name} - {program} (Year: {census_year.year}) "
                            f"(Required: {metrics['required_sites']}, "
                            f"Actual: {metrics['actual_sites']}, "
                            f"Shortfall: {metrics['shortfall']})"
                        )
        
        result_msg = (
            f"Compliance calculations completed: {total_calculations} records created "
            f"for {total_communities} communities in year {census_year.year}. Time: {now_str}"
        )
        logger.info(result_msg)
        return result_msg
        
    except Exception as e:
        logger.error(f"Error in compliance calculation task: {str(e)}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def calculate_community_compliance(self, community_id: str, program: str = None, census_year_id: int = None):
    """
    Calculate compliance for a specific community in a specific census year.
    Only calculates if the community is active in that census year.
    
    Args:
        community_id: UUID of the community
        program: Optional specific program (if None, calculates all programs)
        census_year_id: Optional census year ID (if None, uses latest census year for community)
    """
    try:
        community = Community.objects.get(id=community_id)
        
        # Get census year
        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=census_year_id)
            except CensusYear.DoesNotExist:
                logger.error(f"Census year with id {census_year_id} not found")
                raise
        else:
            # Get the latest census year for this community
            latest_census_data = community.census_data.order_by('-census_year__year').first()
            if latest_census_data:
                census_year = latest_census_data.census_year
            else:
                logger.error(f"No census data found for community {community_id}")
                return []
        
        # Check if community is active in this census year
        try:
            community_census = CommunityCensusData.objects.get(
                community=community,
                census_year=census_year
            )
            if not community_census.is_active:
                logger.info(f"Community {community.name} is not active in year {census_year.year}. Skipping compliance calculation.")
                return []
        except CommunityCensusData.DoesNotExist:
            logger.warning(f"No census data found for community {community.name} in year {census_year.year}. Skipping compliance calculation.")
            return []
        
        programs = [program] if program else ['Paint', 'Lighting', 'Solvents', 'Pesticides']
        
        results = []
        
        with transaction.atomic():
            for prog in programs:
                # Calculate compliance metrics (returns zeros if inactive)
                metrics = calculate_compliance(community, prog, census_year)
                
                # Create or update compliance calculation record (even with zero values)
                calc = ComplianceCalculation.objects.update_or_create(
                    community=community,
                    program=prog,
                    census_year=census_year,
                    defaults={
                        'required_sites': metrics['required_sites'],
                        'actual_sites': metrics['actual_sites'],
                        'shortfall': metrics['shortfall'],
                        'excess': metrics['excess'],
                        'compliance_rate': metrics['compliance_rate'],
                        'created_by': None
                    }
                )
                
                # Log if zero compliance (inactive)
                if all(v == 0 for v in [metrics['required_sites'], metrics['actual_sites'], metrics['compliance_rate']]):
                    logger.info(
                        f"Zero compliance saved for {community.name} - {prog} "
                        f"(Year: {census_year.year}): inactive community or no active rules"
                    )
                
                results.append({
                    'program': prog,
                    'compliance_rate': metrics['compliance_rate'],
                    'shortfall': metrics['shortfall'],
                    'census_year': census_year.year
                })
        
        logger.info(f"Compliance calculated for {community.name} (Year: {census_year.year}): {results}")
        return results
        
    except Community.DoesNotExist:
        logger.error(f"Community with id {community_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error calculating compliance for community {community_id}: {str(e)}")
        raise

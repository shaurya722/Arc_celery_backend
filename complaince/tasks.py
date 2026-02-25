"""
Celery tasks for compliance calculations.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from community.models import Community
from complaince.models import ComplianceCalculation
from complaince.utils import calculate_compliance

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def calculate_all_compliance(self):
    """
    Calculate compliance for all active communities and programs.
    Runs periodically to update compliance metrics.
    """
    try:
        now = timezone.now()
        local_now = timezone.localtime(now)
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        programs = ['Paint', 'Lighting', 'Solvents', 'Pesticides']
        
        # Get all active communities
        communities = Community.objects.filter(is_active=True)
        
        total_calculations = 0
        total_communities = communities.count()
        
        logger.info(f"Starting compliance calculations for {total_communities} communities at {now_str}")
        
        with transaction.atomic():
            for community in communities:
                for program in programs:
                    # Calculate compliance metrics
                    metrics = calculate_compliance(community, program)
                    
                    # Create or update compliance calculation record
                    ComplianceCalculation.objects.update_or_create(
                        community=community,
                        program=program,
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
                    
                    # Log non-compliant communities
                    if metrics['shortfall'] > 0:
                        logger.warning(
                            f"Non-compliant: {community.name} - {program} "
                            f"(Required: {metrics['required_sites']}, "
                            f"Actual: {metrics['actual_sites']}, "
                            f"Shortfall: {metrics['shortfall']})"
                        )
        
        result_msg = (
            f"Compliance calculations completed: {total_calculations} records created "
            f"for {total_communities} communities. Time: {ist_time}"
        )
        logger.info(result_msg)
        return result_msg
        
    except Exception as e:
        logger.error(f"Error in compliance calculation task: {str(e)}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def calculate_community_compliance(self, community_id: str, program: str = None):
    """
    Calculate compliance for a specific community.
    
    Args:
        community_id: UUID of the community
        program: Optional specific program (if None, calculates all programs)
    """
    try:
        community = Community.objects.get(id=community_id)
        
        programs = [program] if program else ['Paint', 'Lighting', 'Solvents', 'Pesticides']
        
        results = []
        
        with transaction.atomic():
            for prog in programs:
                metrics = calculate_compliance(community, prog)
                
                calc = ComplianceCalculation.objects.update_or_create(
                    community=community,
                    program=prog,
                    defaults={
                        'required_sites': metrics['required_sites'],
                        'actual_sites': metrics['actual_sites'],
                        'shortfall': metrics['shortfall'],
                        'excess': metrics['excess'],
                        'compliance_rate': metrics['compliance_rate'],
                        'created_by': None
                    }
                )
                
                results.append({
                    'program': prog,
                    'compliance_rate': metrics['compliance_rate'],
                    'shortfall': metrics['shortfall']
                })
        
        logger.info(f"Compliance calculated for {community.name}: {results}")
        return results
        
    except Community.DoesNotExist:
        logger.error(f"Community with id {community_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error calculating compliance for community {community_id}: {str(e)}")
        raise

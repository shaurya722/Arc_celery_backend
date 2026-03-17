"""
Celery tasks for regulatory rules expiry.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import RegulatoryRule, RegulatoryRuleCensusData
from community.models import Community, CommunityCensusData, CensusYear
from sites.models import Site, SiteCensusData

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def check_expiry(self):
    """Deactivate records whose end_date has passed. Uses IST timezone."""
    try:
        now = timezone.now()
        local_now = timezone.localtime(now)
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        with transaction.atomic():
            # Get expired regulatory rule census data before updating
            expired_rule_census = RegulatoryRuleCensusData.objects.filter(
                end_date__lt=now, 
                is_active=True
            ).select_related('regulatory_rule', 'census_year')
            rule_census_ids = list(expired_rule_census.values_list(
                'id', 'regulatory_rule__name', 'census_year__id'
            ))
            rule_census_count = expired_rule_census.update(is_active=False)
            
            # Get expired community census data before updating
            expired_community_census = CommunityCensusData.objects.filter(
                end_date__lt=now, 
                is_active=True
            ).select_related('community', 'census_year')
            community_census_ids = list(expired_community_census.values_list(
                'id', 'community__name', 'census_year__id'
            ))
            community_census_count = expired_community_census.update(is_active=False)
            
            # Get expired site census data before updating
            expired_site_census = SiteCensusData.objects.filter(
                site_end_date__lt=now, 
                is_active=True
            ).select_related('site', 'community', 'census_year')
            site_census_ids = list(expired_site_census.values_list(
                'id', 'site__site_name', 'census_year__id'
            ))
            site_census_count = expired_site_census.update(is_active=False)
        
        # Trigger compliance recalculation after transaction commit
        from complaince.tasks import calculate_community_compliance
        
        # For expired community census data
        for _, community_name, census_year in community_census_ids:
            try:
                community = Community.objects.get(name=community_name)
                calculate_community_compliance.delay(str(community.id), census_year_id=census_year)
            except Community.DoesNotExist:
                logger.warning(f"Community '{community_name}' not found for compliance recalculation")
        
        # For expired site census data
        for _, site_name, census_year in site_census_ids:
            try:
                site = Site.objects.get(site_name=site_name)
                if site.community_id:
                    calculate_community_compliance.delay(str(site.community_id), census_year_id=census_year)
            except Site.DoesNotExist:
                logger.warning(f"Site '{site_name}' not found for compliance recalculation")
        
        # For expired regulatory rule census data - recalculate all affected communities
        affected_communities = set()
        for _, rule_name, census_year in rule_census_ids:
            try:
                rule = RegulatoryRule.objects.get(name=rule_name)
                # Find communities that might be affected by this rule
                communities = CommunityCensusData.objects.filter(
                    census_year__year=census_year,
                    is_active=True
                ).values_list('community_id', flat=True)
                affected_communities.update(communities)
            except RegulatoryRule.DoesNotExist:
                logger.warning(f"Regulatory rule '{rule_name}' not found")
        
        # Trigger compliance recalculation for communities affected by rule changes
        for community_id in affected_communities:
            calculate_community_compliance.delay(str(community_id), census_year_id=census_year)
        
        # Deactivate expired programs
        program_fields = [
            ('program_paint', 'program_paint_end_date', 'program_paint_start_date'),
            ('program_lights', 'program_lights_end_date', 'program_lights_start_date'),
            ('program_solvents', 'program_solvents_end_date', 'program_solvents_start_date'),
            ('program_pesticides', 'program_pesticides_end_date', 'program_pesticides_start_date'),
            ('program_fertilizers', 'program_fertilizers_end_date', 'program_fertilizers_start_date'),
        ]
        program_updates = {}
        affected_communities = set()
        for program_bool, end_date_field, start_date_field in program_fields:
            # Get communities affected before update
            site_census = SiteCensusData.objects.filter(
                **{end_date_field + '__lt': now, program_bool: True}
            ).values_list('community_id', flat=True).distinct()
            affected_communities.update(site_census)
            count = SiteCensusData.objects.filter(
                **{end_date_field + '__lt': now, program_bool: True}
            ).update(**{program_bool: False, start_date_field: None, end_date_field: None})
            if count > 0:
                program_updates[program_bool] = count
        
        # Trigger compliance recalculation for affected communities
        from complaince.tasks import calculate_community_compliance
        for community_id in affected_communities:
            if community_id:
                # Get latest census year for this community
                latest_census = CommunityCensusData.objects.filter(
                    community_id=community_id
                ).order_by('-census_year__year').first()
                if latest_census:
                    calculate_community_compliance.delay(str(community_id), census_year_id=latest_census.census_year.id)
        
        # Log changes
        now_str = now.strftime('%Y-%m-%d %H:%M:%S IST')
        if rule_census_count > 0:
            logger.info(f"Expired {rule_census_count} Regulatory Rule Census Data (IST: {now_str}): {', '.join([f'{name} (Year:{year})' for _, name, year in rule_census_ids])}")
        
        if community_census_count > 0:
            logger.info(f"Expired {community_census_count} Community Census Data (IST: {now_str}): {', '.join([f'{name} (Year:{year})' for _, name, year in community_census_ids])}")
        
        if site_census_count > 0:
            logger.info(f"Expired {site_census_count} Site Census Data (IST: {now_str}): {', '.join([f'{name} (Year:{year})' for _, name, year in site_census_ids])}")
        
        for program, count in program_updates.items():
            logger.info(f"Deactivated {count} {program} programs (IST: {now_str})")
        
        if rule_census_count == 0 and community_census_count == 0 and site_census_count == 0 and not program_updates:
            logger.info(f"No expired records found at {now_str}")
        
        rule_names = ', '.join([f"{name}(Y{year})" for _, name, year in rule_census_ids]) if rule_census_ids else 'None'
        community_names = ', '.join([f"{name}(Y{year})" for _, name, year in community_census_ids]) if community_census_ids else 'None'
        site_names = ', '.join([f"{name}(Y{year})" for _, name, year in site_census_ids]) if site_census_ids else 'None'
        
        result = f"Rules updated: {rule_census_count} ({rule_names}). Communities updated: {community_census_count} ({community_names}). Sites updated: {site_census_count} ({site_names}). Time: {now_str}"
        return result
        
    except Exception as e:
        logger.error(f"Error in check_expiry task: {str(e)}")
        return f"Error occurred: {str(e)}"

"""
Celery tasks for regulatory rules expiry.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import RegulatoryRule
from community.models import Community
from sites.models import Site

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def check_expiry(self):
    """Deactivate records whose end_date has passed. Uses IST timezone."""
    try:
        now = timezone.now()
        local_now = timezone.localtime(now)
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        with transaction.atomic():
            # Get expired rules before updating
            expired_rules = RegulatoryRule.objects.filter(end_date__lt=now, is_active=True)
            rule_ids = list(expired_rules.values_list('id', 'name'))
            rule_count = expired_rules.update(is_active=False)
            
            # Expire communities individually to trigger signals
            expired_communities = Community.objects.filter(end_date__lt=now, is_active=True)
            community_ids = []
            for community in expired_communities:
                community.is_active = False
                community.save()
                community_ids.append((str(community.id), community.name))
            community_count = len(community_ids)
            
            # Expire sites individually to trigger signals
            expired_sites = Site.objects.filter(site_end_date__lt=now, is_active=True)
            site_ids = []
            for site in expired_sites:
                site.is_active = False
                site.save()
                site_ids.append((str(site.id), site.site_name))
            site_count = len(site_ids)
        
        # Trigger compliance recalculation after transaction commit
        from complaince.tasks import calculate_community_compliance
        for community_id, _ in community_ids:
            calculate_community_compliance(community_id)
        for site in expired_sites:
            if site.community_id:
                calculate_community_compliance(str(site.community_id))
        
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
            communities = Site.objects.filter(**{end_date_field + '__lt': now, program_bool: True}).values_list('community_id', flat=True).distinct()
            affected_communities.update(communities)
            count = Site.objects.filter(**{end_date_field + '__lt': now, program_bool: True}).update(**{program_bool: False, start_date_field: None, end_date_field: None})
            if count > 0:
                program_updates[program_bool] = count
        
        # Trigger compliance recalculation for affected communities
        from complaince.tasks import calculate_community_compliance
        for community_id in affected_communities:
            if community_id:
                calculate_community_compliance(str(community_id))
        
        # Log changes
        now_str = now.strftime('%Y-%m-%d %H:%M:%S IST')
        if rule_count > 0:
            logger.info(f"Expired {rule_count} Regulatory Rules (IST: {now_str}): {', '.join([f'{name} (ID:{id})' for id, name in rule_ids])}")
        
        if community_count > 0:
            logger.info(f"Expired {community_count} Communities (IST: {now_str}): {', '.join([f'{name} (ID:{id})' for id, name in community_ids])}")
        
        if site_count > 0:
            logger.info(f"Expired {site_count} Sites (IST: {now_str}): {', '.join([f'{name} (ID:{id})' for id, name in site_ids])}")
        
        for program, count in program_updates.items():
            logger.info(f"Deactivated {count} {program} programs (IST: {now_str})")
        
        if rule_count == 0 and community_count == 0 and site_count == 0 and not program_updates:
            logger.info(f"No expired records found at {now_str}")
        
        rule_names = ', '.join([name for _, name in rule_ids]) if rule_ids else 'None'
        community_names = ', '.join([name for _, name in community_ids]) if community_ids else 'None'
        site_names = ', '.join([name for _, name in site_ids]) if site_ids else 'None'
        
        result = f"Rules updated: {rule_count} ({rule_names}). Communities updated: {community_count} ({community_names}). Sites updated: {site_count} ({site_names}). Time: {now_str}"
        return result
        
    except Exception as e:
        logger.error(f"Error in check_expiry task: {str(e)}")
        return f"Error occurred: {str(e)}"

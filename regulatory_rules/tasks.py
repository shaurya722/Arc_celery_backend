"""
Celery tasks for regulatory rules expiry.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import RegulatoryRule, RegulatoryRuleCensusData
from community.models import CommunityCensusData
from sites.models import SiteCensusData

logger = logging.getLogger(__name__)

SITE_PROGRAM_FIELDS = [
    ('Paint', 'program_paint', 'program_paint_end_date', 'program_paint_start_date'),
    ('Lighting', 'program_lights', 'program_lights_end_date', 'program_lights_start_date'),
    ('Solvents', 'program_solvents', 'program_solvents_end_date', 'program_solvents_start_date'),
    ('Pesticides', 'program_pesticides', 'program_pesticides_end_date', 'program_pesticides_start_date'),
    ('Fertilizers', 'program_fertilizers', 'program_fertilizers_end_date', 'program_fertilizers_start_date'),
]


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def check_expiry(self):
    """Deactivate records whose end_date has passed. Uses IST timezone."""
    try:
        now = timezone.now()
        local_now = timezone.localtime(now)
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        with transaction.atomic():
            # Expire when end timestamp is reached (inclusive at equality).
            # Get expired regulatory rule census data before updating
            expired_rule_census = RegulatoryRuleCensusData.objects.filter(
                end_date__lte=now,
                is_active=True,
            ).select_related('regulatory_rule', 'census_year')
            rule_census_rows = list(
                expired_rule_census.values_list(
                    'id', 'regulatory_rule__name', 'census_year__id'
                )
            )
            rule_census_count = expired_rule_census.update(is_active=False)

            # Get expired community census data before updating
            expired_community_census = CommunityCensusData.objects.filter(
                end_date__lte=now,
                is_active=True,
            ).select_related('community', 'census_year')
            community_census_rows = list(
                expired_community_census.values_list(
                    'community_id', 'community__name', 'census_year__id'
                )
            )
            community_census_count = expired_community_census.update(is_active=False)

            # Site rows: bulk update bypasses model.save(); clear event_approved so Event
            # rows stay inactive on later saves (save() syncs is_active from event_approved).
            expired_site_census = SiteCensusData.objects.filter(
                site_end_date__lte=now,
            ).filter(
                Q(is_active=True)
                | Q(event_approved=True)
                | Q(program_paint=True)
                | Q(program_lights=True)
                | Q(program_solvents=True)
                | Q(program_pesticides=True)
                | Q(program_fertilizers=True)
            ).select_related('site', 'community', 'census_year')
            site_census_rows = list(
                expired_site_census.values_list(
                    'id', 'site__site_name', 'community_id', 'census_year__id'
                )
            )
            expired_site_updates = {
                'is_active': False,
                'event_approved': False,
            }
            for _program, program_bool, end_date_field, start_date_field in SITE_PROGRAM_FIELDS:
                expired_site_updates[program_bool] = False
                expired_site_updates[start_date_field] = None
                expired_site_updates[end_date_field] = None
            site_census_count = expired_site_census.update(**expired_site_updates)
        
        # Trigger compliance recalculation after transaction commit
        from complaince.tasks import schedule_community_compliance_recalc

        # For expired community census data (use FK ids; names can collide)
        for community_id, community_name, census_year_id in community_census_rows:
            if community_id:
                schedule_community_compliance_recalc(community_id, census_year_id)
            else:
                logger.warning(
                    'Skipped compliance recalc for expired community census (no community_id): %s',
                    community_name,
                )

        # For expired site census data, use the census row's community + year
        for _sid, site_name, community_id, census_year_id in site_census_rows:
            if community_id and census_year_id:
                schedule_community_compliance_recalc(community_id, census_year_id)
            else:
                logger.warning(
                    'Skipped compliance recalc for expired site census %s (missing community or year)',
                    site_name,
                )

        # Expired regulatory rule census: recalc communities in that census year
        # (census_year_id from values_list is the CensusYear PK, not the calendar year).
        rule_recalc_pairs = set()
        for _rid, rule_name, census_year_id in rule_census_rows:
            try:
                RegulatoryRule.objects.get(name=rule_name)
            except RegulatoryRule.DoesNotExist:
                logger.warning("Regulatory rule '%s' not found after expiry update", rule_name)
                continue
            for cid in CommunityCensusData.objects.filter(
                census_year_id=census_year_id,
                is_active=True,
            ).values_list('community_id', flat=True):
                if cid:
                    rule_recalc_pairs.add((cid, census_year_id))

        for community_id, census_year_id in rule_recalc_pairs:
            schedule_community_compliance_recalc(community_id, census_year_id)
        
        # Deactivate expired site programs independently from site row expiry.
        program_updates = {}
        program_recalc_pairs = set()
        for program_name, program_bool, end_date_field, start_date_field in SITE_PROGRAM_FIELDS:
            expired_program_qs = SiteCensusData.objects.filter(
                **{end_date_field + '__lte': now, program_bool: True}
            )
            affected_rows = list(
                expired_program_qs.values_list('community_id', 'census_year_id').distinct()
            )
            for community_id, census_year_id in affected_rows:
                if community_id and census_year_id:
                    program_recalc_pairs.add((community_id, census_year_id, program_name))

            count = expired_program_qs.update(
                **{program_bool: False, start_date_field: None, end_date_field: None}
            )
            if count > 0:
                program_updates[program_bool] = count
        
        # Trigger compliance recalculation for affected communities/programs.
        for community_id, census_year_id, program_name in program_recalc_pairs:
            schedule_community_compliance_recalc(
                community_id,
                census_year_id,
                program=program_name,
            )
        
        # Log changes
        now_str = local_now.strftime('%Y-%m-%d %H:%M:%S %Z')
        if rule_census_count > 0:
            logger.info(
                f"Expired {rule_census_count} Regulatory Rule Census Data (IST: {now_str}): "
                f"{', '.join([f'{name} (census_year_id:{cy})' for _, name, cy in rule_census_rows])}"
            )

        if community_census_count > 0:
            logger.info(
                f"Expired {community_census_count} Community Census Data (IST: {now_str}): "
                f"{', '.join([f'{name} (census_year_id:{cy})' for _cid, name, cy in community_census_rows])}"
            )

        if site_census_count > 0:
            logger.info(
                f"Expired {site_census_count} Site Census Data (IST: {now_str}): "
                f"{', '.join([f'{name} (census_year_id:{cy})' for _sid, name, _cid, cy in site_census_rows])}"
            )
        
        for program, count in program_updates.items():
            logger.info(f"Deactivated {count} {program} programs (IST: {now_str})")
        
        if rule_census_count == 0 and community_census_count == 0 and site_census_count == 0 and not program_updates:
            logger.info(f"No expired records found at {now_str}")
        
        rule_names = (
            ', '.join([f"{name}(cy:{cy})" for _, name, cy in rule_census_rows])
            if rule_census_rows
            else 'None'
        )
        community_names = (
            ', '.join([f"{name}(cy:{cy})" for _cid, name, cy in community_census_rows])
            if community_census_rows
            else 'None'
        )
        site_names = (
            ', '.join([f"{name}(cy:{cy})" for _sid, name, _cid, cy in site_census_rows])
            if site_census_rows
            else 'None'
        )
        
        result = f"Rules updated: {rule_census_count} ({rule_names}). Communities updated: {community_census_count} ({community_names}). Sites updated: {site_census_count} ({site_names}). Time: {now_str}"
        return result
        
    except Exception as e:
        logger.error(f"Error in check_expiry task: {str(e)}")
        return f"Error occurred: {str(e)}"

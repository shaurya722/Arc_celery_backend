"""
Signals for automatic compliance recalculation when underlying data changes.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from community.models import CommunityCensusData, CensusYear
from sites.models import SiteCensusData
from regulatory_rules.models import RegulatoryRuleCensusData
from .tasks import calculate_community_compliance

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CommunityCensusData)
def recalculate_compliance_on_community_change(sender, instance, created, **kwargs):
    """
    Recalculate compliance for a community when its census data changes.
    If community becomes inactive, set compliance to zero.
    If community is active, recalculate compliance for all programs.
    """
    try:
        from .models import ComplianceCalculation
        
        if instance.is_active:
            # Community is active - recalculate compliance
            logger.info(
                f"Community data changed for {instance.community.name} in year {instance.census_year.year}. "
                f"Triggering compliance recalculation."
            )

            # Trigger async compliance calculation
            calculate_community_compliance.delay(
                community_id=str(instance.community.id),
                census_year_id=instance.census_year.id
            )
        else:
            # Community is inactive - set all compliance to zero
            updated_count = ComplianceCalculation.objects.filter(
                community=instance.community,
                census_year=instance.census_year
            ).update(
                required_sites=0,
                actual_sites=0,
                shortfall=0,
                excess=0,
                compliance_rate=0.0
            )
            
            logger.info(
                f"Community {instance.community.name} is inactive in year {instance.census_year.year}. "
                f"Set {updated_count} compliance calculation(s) to zero."
            )
    except Exception as e:
        logger.error(
            f"Error handling compliance for community {instance.community.name}: {str(e)}"
        )


@receiver(post_save, sender=SiteCensusData)
def recalculate_compliance_on_site_change(sender, instance, created, **kwargs):
    """
    Recalculate compliance for a community when site data changes in that community.
    This will recalculate compliance for programs that might be affected by site changes.
    """
    try:
        # Only recalculate if the site is active in this census year
        if instance.is_active:
            logger.info(
                f"Site data changed for site '{instance.site.site_name}' in community "
                f"'{instance.community.name}' for year {instance.census_year.year}. "
                f"Triggering compliance recalculation."
            )

            # Trigger compliance calculation for the affected community
            calculate_community_compliance.delay(
                community_id=str(instance.community.id),
                census_year_id=instance.census_year.id
            )
    except Exception as e:
        logger.error(
            f"Error triggering compliance recalculation for site {instance.site.site_name}: {str(e)}"
        )


@receiver(post_save, sender=RegulatoryRuleCensusData)
def recalculate_compliance_on_rule_change(sender, instance, created, **kwargs):
    """
    Recalculate compliance for all affected communities when regulatory rule changes.
    If rule becomes inactive, set compliance to zero for that program (if no other active rules).
    If rule is active, recalculate compliance for all communities in the census year where the rule applies.
    """
    try:
        from .models import ComplianceCalculation
        
        if instance.is_active:
            # Rule is active - recalculate compliance
            logger.info(
                f"Regulatory rule '{instance.regulatory_rule.name}' changed for year {instance.census_year.year}. "
                f"Triggering compliance recalculation for all affected communities."
            )

            # Get all communities that are active in this census year and might be affected by this rule
            affected_communities = CommunityCensusData.objects.filter(
                census_year=instance.census_year,
                is_active=True
            ).select_related('community')

            # Trigger compliance recalculation for each affected community
            for community_data in affected_communities:
                # Check if the rule applies to this community's population range
                rule_applies = (
                    (instance.min_population is None or community_data.population >= instance.min_population) and
                    (instance.max_population is None or community_data.population <= instance.max_population)
                )

                if rule_applies:
                    logger.info(
                        f"Rule '{instance.regulatory_rule.name}' applies to community "
                        f"'{community_data.community.name}' (population: {community_data.population}). "
                        f"Triggering compliance recalculation."
                    )

                    calculate_community_compliance.delay(
                        community_id=str(community_data.community.id),
                        census_year_id=instance.census_year.id
                    )
        else:
            # Rule is inactive - check if there are any other active rules for this program
            other_active_rules = RegulatoryRuleCensusData.objects.filter(
                program=instance.program,
                census_year=instance.census_year,
                is_active=True
            ).exclude(id=instance.id).exists()
            
            if not other_active_rules:
                # No other active rules for this program - set compliance to zero
                updated_count = ComplianceCalculation.objects.filter(
                    program=instance.program,
                    census_year=instance.census_year
                ).update(
                    required_sites=0,
                    actual_sites=0,
                    shortfall=0,
                    excess=0,
                    compliance_rate=0.0
                )
                
                logger.info(
                    f"Regulatory rule '{instance.regulatory_rule.name}' for program '{instance.program}' "
                    f"is inactive in year {instance.census_year.year} and no other active rules exist. "
                    f"Set {updated_count} compliance calculation(s) to zero."
                )
            else:
                # Other active rules exist - recalculate compliance
                logger.info(
                    f"Regulatory rule '{instance.regulatory_rule.name}' is inactive but other active rules exist. "
                    f"Triggering compliance recalculation."
                )
                
                affected_communities = CommunityCensusData.objects.filter(
                    census_year=instance.census_year,
                    is_active=True
                ).select_related('community')
                
                for community_data in affected_communities:
                    calculate_community_compliance.delay(
                        community_id=str(community_data.community.id),
                        program=instance.program,
                        census_year_id=instance.census_year.id
                    )
    except Exception as e:
        logger.error(
            f"Error handling compliance for rule {instance.regulatory_rule.name}: {str(e)}"
        )


@receiver(post_delete, sender=CommunityCensusData)
def recalculate_compliance_on_community_delete(sender, instance, **kwargs):
    """
    Handle compliance recalculation when community census data is deleted.
    """
    try:
        logger.info(
            f"Community data deleted for {instance.community.name} in year {instance.census_year.year}. "
            f"Compliance records may need manual cleanup."
        )
        # Note: We don't automatically recalculate on delete as the data is gone
        # But we log it for awareness
    except Exception as e:
        logger.error(f"Error handling community data deletion: {str(e)}")


@receiver(post_delete, sender=SiteCensusData)
def recalculate_compliance_on_site_delete(sender, instance, **kwargs):
    """
    Recalculate compliance when site data is deleted.
    """
    try:
        logger.info(
            f"Site data deleted for site '{instance.site.site_name}' in community "
            f"'{instance.community.name}' for year {instance.census_year.year}. "
            f"Triggering compliance recalculation."
        )

        # Trigger compliance recalculation for the affected community
        calculate_community_compliance.delay(
            community_id=str(instance.community.id),
            census_year_id=instance.census_year.id
        )
    except Exception as e:
        logger.error(f"Error triggering compliance recalculation for site deletion: {str(e)}")


@receiver(post_delete, sender=RegulatoryRuleCensusData)
def recalculate_compliance_on_rule_delete(sender, instance, **kwargs):
    """
    Recalculate compliance for all affected communities when regulatory rule is deleted.
    """
    try:
        logger.info(
            f"Regulatory rule '{instance.regulatory_rule.name}' deleted for year {instance.census_year.year}. "
            f"Triggering compliance recalculation for all affected communities."
        )

        # Get all communities that were affected by this rule
        affected_communities = CommunityCensusData.objects.filter(
            census_year=instance.census_year,
            is_active=True
        ).select_related('community')

        # Trigger compliance recalculation for each affected community
        for community_data in affected_communities:
            calculate_community_compliance.delay(
                community_id=str(community_data.community.id),
                census_year_id=instance.census_year.id
            )
    except Exception as e:
        logger.error(f"Error triggering compliance recalculation for rule deletion: {str(e)}")

"""
Business logic layer for site reallocation.
DO NOT use signals for this - use explicit service methods.
"""
from collections import defaultdict

from django.db import transaction
from django.core.exceptions import ValidationError
from .models import SiteCensusData, SiteReallocation
from community.models import Community, AdjacentCommunity


class SiteReallocationService:
    """
    Service layer for handling site reallocation business logic.
    This ensures proper validation, audit trail, and async recalculation.
    """
    
    @staticmethod
    def reallocate(site_census_data, to_community, user=None, reason=None, program=None):
        """
        Reallocate a site from its current effective community to an adjacent community.

        Adjacency: map-drawn Community.adjacent and/or legacy AdjacentCommunity (either direction)
        for the site census year.

        Rules: source must have program excess; target must have program shortfall; inbound
        reallocations to target for that program must be under floor(required × cap% / 100)
        (cap from RegulatoryRuleCensusData Reallocation rule, else 35%).
        """
        from complaince.models import ComplianceCalculation

        from .adjacent_reallocation import (
            PROGRAM_FIELD,
            infer_program_from_site,
            is_adjacent_for_reallocation,
            reallocation_cap_status,
        )

        from_community = site_census_data.effective_community
        census_year = site_census_data.census_year

        # Validation 1: Check if site can be reallocated
        if not site_census_data.is_reallocatable:
            raise ValidationError(
                f"Site '{site_census_data.site.site_name}' cannot be reallocated. "
                f"Site type: {site_census_data.site_type}, "
                f"Operator type: {site_census_data.operator_type}"
            )

        # Validation 2: Check if from and to communities are the same
        if from_community == to_community:
            raise ValidationError(
                f"Cannot reallocate to the same community: {from_community.name}"
            )

        resolved_program = program or infer_program_from_site(site_census_data)
        if not resolved_program:
            raise ValidationError(
                'Could not infer program from site flags; pass program (Paint, Lighting, '
                'Solvents, Pesticides, or Fertilizers).'
            )
        if resolved_program not in PROGRAM_FIELD:
            raise ValidationError(f'Invalid program: {resolved_program}')

        field = PROGRAM_FIELD[resolved_program]
        if not getattr(site_census_data, field, False):
            raise ValidationError(
                f"Site '{site_census_data.site.site_name}' does not participate in "
                f"{resolved_program}; cannot reallocate under that program."
            )

        # Validation 3: Adjacency (map boundary + legacy AdjacentCommunity)
        if not is_adjacent_for_reallocation(from_community, to_community, census_year):
            raise ValidationError(
                f"'{to_community.name}' is not adjacent to '{from_community.name}' for census year "
                f"{census_year.year} (map adjacency or adjacent-community record)."
            )

        # Validation 4: Source excess / target shortfall / regulatory cap
        src_calc = ComplianceCalculation.objects.filter(
            community=from_community,
            census_year=census_year,
            program=resolved_program,
        ).first()
        if not src_calc or (src_calc.excess or 0) < 1:
            raise ValidationError(
                f"Source community '{from_community.name}' has no excess for {resolved_program} "
                f"in census year {census_year.year}."
            )

        tgt_calc = ComplianceCalculation.objects.filter(
            community=to_community,
            census_year=census_year,
            program=resolved_program,
        ).first()
        if not tgt_calc or (tgt_calc.shortfall or 0) < 1:
            raise ValidationError(
                f"Target community '{to_community.name}' has no shortfall for {resolved_program} "
                f"in census year {census_year.year}."
            )

        cap = reallocation_cap_status(
            to_community, census_year, resolved_program, tgt_calc.required_sites or 0
        )
        if cap['inbound_reallocations_remaining'] < 1:
            raise ValidationError(
                f"Inbound reallocation cap reached for '{to_community.name}' ({resolved_program}): "
                f"max {cap['max_inbound_reallocations']} sites "
                f"({cap['regulatory_reallocation_percentage']}% of "
                f"{tgt_calc.required_sites} required), {cap['inbound_reallocations_used']} used."
            )

        # Validation 5: Check if site is active
        if not site_census_data.is_active:
            raise ValidationError(
                f"Cannot reallocate inactive site '{site_census_data.site.site_name}'"
            )
        
        # Create reallocation record (preserves history)
        with transaction.atomic():
            reallocation = SiteReallocation.objects.create(
                site_census_data=site_census_data,
                from_community=from_community,
                to_community=to_community,
                census_year=site_census_data.census_year,
                created_by=user,
                reason=reason
            )
            
            # Trigger async recalculation for both communities
            from complaince.tasks import calculate_community_compliance
            calculate_community_compliance.delay(
                str(from_community.id), 
                census_year_id=site_census_data.census_year.id
            )
            calculate_community_compliance.delay(
                str(to_community.id), 
                census_year_id=site_census_data.census_year.id
            )
        
        return reallocation
    
    @staticmethod
    def undo_reallocation(reallocation_id, user=None):
        """
        Undo a reallocation by deleting the reallocation record.
        The site will revert to its previous community (or original if no other reallocations).
        
        Args:
            reallocation_id: UUID of the SiteReallocation to undo
            user: User performing the undo (optional)
            
        Returns:
            dict with undo details
        """
        try:
            reallocation = SiteReallocation.objects.get(id=reallocation_id)
        except SiteReallocation.DoesNotExist:
            raise ValidationError(f"Reallocation {reallocation_id} not found")
        
        site_census_data = reallocation.site_census_data
        from_community = reallocation.from_community
        to_community = reallocation.to_community
        census_year = reallocation.census_year
        
        with transaction.atomic():
            reallocation.delete()
            
            # Trigger recalculation for both communities
            from complaince.tasks import calculate_community_compliance
            calculate_community_compliance.delay(
                str(from_community.id), 
                census_year_id=census_year.id
            )
            calculate_community_compliance.delay(
                str(to_community.id), 
                census_year_id=census_year.id
            )
        
        return {
            'message': 'Reallocation undone successfully',
            'site': site_census_data.site.site_name,
            'reverted_from': to_community.name,
            'reverted_to': from_community.name
        }
    
    @staticmethod
    def get_reallocation_history(site_census_data):
        """
        Get full reallocation history for a site.
        
        Args:
            site_census_data: SiteCensusData instance
            
        Returns:
            QuerySet of SiteReallocation ordered by date
        """
        return site_census_data.reallocations.select_related(
            'from_community', 'to_community', 'created_by'
        ).order_by('-reallocated_at')
    
    @staticmethod
    def get_adjacent_communities_with_allocation(source_community, census_year, program=None):
        """
        Get adjacent communities with their compliance status and allocated sites.
        
        Args:
            source_community: Community instance
            census_year: CensusYear instance
            program: Optional program filter (e.g., 'Paint', 'Lighting')
            
        Returns:
            dict with source community compliance and adjacent communities data
        """
        from complaince.models import ComplianceCalculation
        from django.db.models import Q, Count
        
        # Get source community compliance
        source_compliance = {}
        if program:
            compliance_records = ComplianceCalculation.objects.filter(
                community=source_community,
                census_year=census_year,
                program=program
            ).first()
        else:
            compliance_records = ComplianceCalculation.objects.filter(
                community=source_community,
                census_year=census_year
            )
        
        if program and compliance_records:
            source_compliance = {
                'required': compliance_records.required_sites,
                'actual': compliance_records.actual_sites,
                'shortfall': compliance_records.shortfall,
                'excess': compliance_records.excess,
                'compliance_rate': float(compliance_records.compliance_rate)
            }
        elif not program and compliance_records.exists():
            # Aggregate across all programs
            total_required = sum(c.required_sites for c in compliance_records)
            total_actual = sum(c.actual_sites for c in compliance_records)
            total_shortfall = sum(c.shortfall for c in compliance_records)
            total_excess = sum(c.excess for c in compliance_records)
            
            source_compliance = {
                'required': total_required,
                'actual': total_actual,
                'shortfall': total_shortfall,
                'excess': total_excess,
                'compliance_rate': round((total_actual / total_required * 100) if total_required > 0 else 0, 2)
            }
        
        from .adjacent_reallocation import neighbors_for_reallocation

        adj_community_list = neighbors_for_reallocation(source_community, census_year)
        adjacent_communities = []
        
        for adj_community in adj_community_list:
            
            # Get compliance for adjacent community
            if program:
                adj_compliance = ComplianceCalculation.objects.filter(
                    community=adj_community,
                    census_year=census_year,
                    program=program
                ).first()
                
                adj_data = {
                    'id': str(adj_community.id),
                    'community': adj_community.name,
                    'shortfall': adj_compliance.shortfall if adj_compliance else 0,
                    'excess': adj_compliance.excess if adj_compliance else 0,
                    'required': adj_compliance.required_sites if adj_compliance else 0,
                    'actual': adj_compliance.actual_sites if adj_compliance else 0
                }
            else:
                adj_compliance_records = ComplianceCalculation.objects.filter(
                    community=adj_community,
                    census_year=census_year
                )
                
                total_shortfall = sum(c.shortfall for c in adj_compliance_records)
                total_excess = sum(c.excess for c in adj_compliance_records)
                total_required = sum(c.required_sites for c in adj_compliance_records)
                total_actual = sum(c.actual_sites for c in adj_compliance_records)
                
                adj_data = {
                    'id': str(adj_community.id),
                    'community': adj_community.name,
                    'shortfall': total_shortfall,
                    'excess': total_excess,
                    'required': total_required,
                    'actual': total_actual
                }
            
            adjacent_communities.append(adj_data)
        
        # Get sites allocated FROM source community TO adjacent communities
        allocated_from_source = SiteReallocation.objects.filter(
            from_community=source_community,
            census_year=census_year
        ).select_related('to_community', 'site_census_data__site')
        
        allocated_from_adjacent = []
        for reallocation in allocated_from_source:
            site_data = {
                'id': str(reallocation.id),
                'site_name': reallocation.site_census_data.site.site_name,
                'to_community': reallocation.to_community.name,
                'to_community_id': str(reallocation.to_community.id),
                'reallocated_at': reallocation.reallocated_at.isoformat(),
                'reason': reallocation.reason
            }
            allocated_from_adjacent.append(site_data)
        
        return {
            'source_community': source_community.name,
            'compliance': source_compliance,
            'adjacent_communities': adjacent_communities,
            'allocated_from_adjacent': allocated_from_adjacent
        }

    @staticmethod
    def get_excess_communities_overview(census_year, program=None):
        """
        Return a list of communities with excess capacity and their adjacent communities' shortfalls
        along with allocation details.
        """
        from complaince.models import ComplianceCalculation

        compliance_qs = ComplianceCalculation.objects.filter(
            census_year=census_year
        ).select_related('community')

        if program:
            compliance_qs = compliance_qs.filter(program=program)

        # Aggregate compliance metrics per community
        community_metrics = {}
        program_breakdown = defaultdict(list)

        for calc in compliance_qs:
            metrics = community_metrics.setdefault(calc.community_id, {
                'community': calc.community,
                'required': 0,
                'actual': 0,
                'shortfall': 0,
                'excess': 0,
            })

            metrics['required'] += calc.required_sites or 0
            metrics['actual'] += calc.actual_sites or 0
            metrics['shortfall'] += calc.shortfall or 0
            metrics['excess'] += calc.excess or 0

            program_breakdown[calc.community_id].append({
                'program': calc.program,
                'required': calc.required_sites,
                'actual': calc.actual_sites,
                'shortfall': calc.shortfall,
                'excess': calc.excess,
                'compliance_rate': float(calc.compliance_rate)
            })

        for community_id, metrics in community_metrics.items():
            required = metrics['required']
            actual = metrics['actual']
            metrics['compliance_rate'] = round((actual / required * 100) if required else 0, 2)
            metrics['community_id'] = str(metrics['community'].id)
            metrics['community_name'] = metrics['community'].name
            metrics['program_breakdown'] = program_breakdown.get(community_id, [])
            metrics.pop('community', None)

        # Group reallocations by from/to communities for quick lookup
        reallocation_map = defaultdict(lambda: defaultdict(list))
        reallocations = SiteReallocation.objects.filter(
            census_year=census_year
        ).select_related('site_census_data__site', 'from_community', 'to_community')

        for realloc in reallocations:
            reallocation_map[realloc.from_community_id][realloc.to_community_id].append(realloc)

        results = []

        adjacency_records = AdjacentCommunity.objects.filter(
            census_year=census_year
        ).select_related('from_community').prefetch_related('to_communities')

        for adjacency in adjacency_records:
            source_metrics = community_metrics.get(adjacency.from_community_id)
            if not source_metrics:
                community = adjacency.from_community
                source_metrics = {
                    'community_id': str(community.id),
                    'community_name': community.name,
                    'required': 0,
                    'actual': 0,
                    'shortfall': 0,
                    'excess': 0,
                    'compliance_rate': 0,
                    'program_breakdown': []
                }

            adjacent_details = []
            total_allocated = 0

            for dest in adjacency.to_communities.all():
                dest_metrics = community_metrics.get(dest.id, {
                    'required': 0,
                    'actual': 0,
                    'shortfall': 0,
                    'excess': 0,
                    'compliance_rate': 0,
                    'program_breakdown': []
                })

                reallocations_list = reallocation_map.get(adjacency.from_community_id, {}).get(dest.id, [])
                allocated_count = len(reallocations_list)

                total_allocated += allocated_count

                adjacent_details.append({
                    'id': str(dest.id),
                    'community': dest.name,
                    'shortfall': dest_metrics['shortfall'],
                    'excess': dest_metrics['excess'],
                    'required': dest_metrics['required'],
                    'actual': dest_metrics['actual'],
                    'compliance_rate': dest_metrics.get('compliance_rate', 0),
                    'program_breakdown': dest_metrics.get('program_breakdown', []),
                    'allocated_sites': {
                        'count': allocated_count,
                        'sites': [
                            {
                                'reallocation_id': str(realloc.id),
                                'site_census_id': realloc.site_census_data.id,
                                'site_name': realloc.site_census_data.site.site_name,
                                'reallocated_at': realloc.reallocated_at.isoformat()
                            }
                            for realloc in reallocations_list
                        ]
                    }
                })

            if not adjacent_details:
                continue

            allocated_adjacent = [
                adj for adj in adjacent_details if adj['allocated_sites']['count'] > 0
            ]

            results.append({
                'community_id': source_metrics['community_id'],
                'community': source_metrics['community_name'],
                'compliance': {
                    'required': source_metrics['required'],
                    'actual': source_metrics['actual'],
                    'shortfall': source_metrics['shortfall'],
                    'excess': source_metrics['excess'],
                    'compliance_rate': source_metrics['compliance_rate'],
                    'program_breakdown': source_metrics['program_breakdown'],
                },
                'adjacent_communities': adjacent_details,
                'allocated_adjacent_communities': allocated_adjacent,
                'allocated_sites_total': total_allocated
            })

        results.sort(key=lambda item: item['compliance']['excess'], reverse=True)
        return results

    @staticmethod
    def get_map_adjacent_reallocation_overview(source_community, census_year, program):
        """
        Tool C overview: source compliance + neighbors (map + legacy adjacency) with
        shortfall/excess and inbound reallocation cap (regulatory % of target required).
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        from complaince.models import ComplianceCalculation

        from .adjacent_reallocation import (
            DEFAULT_REALLOCATION_PERCENT,
            PROGRAM_FIELD,
            neighbors_for_reallocation,
            reallocation_cap_status,
        )

        if program not in PROGRAM_FIELD:
            raise DjangoValidationError(
                f'Invalid program {program!r}. Expected one of {list(PROGRAM_FIELD)}.'
            )

        source_calc = ComplianceCalculation.objects.filter(
            community=source_community,
            census_year=census_year,
            program=program,
        ).first()

        neighbors = neighbors_for_reallocation(source_community, census_year)
        neighbor_payload = []
        for adj in neighbors:
            cc = ComplianceCalculation.objects.filter(
                community=adj,
                census_year=census_year,
                program=program,
            ).first()
            req = (cc.required_sites if cc else 0) or 0
            neighbor_payload.append(
                {
                    'id': str(adj.id),
                    'name': adj.name,
                    'shortfall': cc.shortfall if cc else 0,
                    'excess': cc.excess if cc else 0,
                    'required': cc.required_sites if cc else 0,
                    'actual': cc.actual_sites if cc else 0,
                    'reallocation_cap': reallocation_cap_status(
                        adj, census_year, program, req
                    ),
                }
            )

        return {
            'source_community': {
                'id': str(source_community.id),
                'name': source_community.name,
            },
            'census_year': {'id': census_year.id, 'year': census_year.year},
            'program': program,
            'cap_rule': (
                f'max_inbound = floor(target_required × percentage / 100); percentage from '
                f'active regulatory rule (rule_type=Reallocation) or {DEFAULT_REALLOCATION_PERCENT}%.'
            ),
            'source_compliance': {
                'required': source_calc.required_sites if source_calc else 0,
                'actual': source_calc.actual_sites if source_calc else 0,
                'shortfall': source_calc.shortfall if source_calc else 0,
                'excess': source_calc.excess if source_calc else 0,
            },
            'adjacent_communities': neighbor_payload,
        }

    @staticmethod
    def get_tool_c_adjacent_reallocation_list(
        census_year,
        program,
        search=None,
        ordering='name',
        page=1,
        page_size=20,
    ):
        """
        Paginated Tool C listing: communities with program excess, eligible sites,
        adjacent neighbors with shortfall (map + legacy adjacency), and reallocation counts.
        Shape matches frontend ToolCAdjacentReallocation expectations.
        """
        import math

        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db.models import Q

        from complaince.models import ComplianceCalculation

        from .adjacent_reallocation import PROGRAM_FIELD, neighbors_for_reallocation

        if program not in PROGRAM_FIELD:
            raise DjangoValidationError(
                f'Invalid program {program!r}. Expected one of {list(PROGRAM_FIELD)}.'
            )

        field = PROGRAM_FIELD[program]
        non_reallocatable_ops = ['Municipal', 'First Nation/Indigenous', 'Regional District']

        calc_qs = ComplianceCalculation.objects.filter(
            census_year=census_year,
            program=program,
            excess__gt=0,
        ).select_related('community')

        if search and str(search).strip():
            calc_qs = calc_qs.filter(community__name__icontains=str(search).strip())

        # Preload reallocations for this year + program (from any source)
        realloc_qs = SiteReallocation.objects.filter(
            census_year=census_year,
            **{f'site_census_data__{field}': True},
        ).select_related('site_census_data__site', 'from_community', 'to_community')

        realloc_by_pair = defaultdict(list)
        for r in realloc_qs:
            realloc_by_pair[(r.from_community_id, r.to_community_id)].append(r)

        rows = []
        for calc in calc_qs:
            comm = calc.community
            excess = calc.excess or 0

            eligible_qs = SiteCensusData.objects.filter(
                community=comm,
                census_year=census_year,
                is_active=True,
                **{field: True},
            ).exclude(site_type='Event').exclude(
                operator_type__in=non_reallocatable_ops
            ).select_related('site')

            eligible_sites = []
            for sc in eligible_qs:
                addr_parts = [sc.address_line_1, sc.address_city, sc.address_postal_code]
                address = ', '.join(p for p in addr_parts if p)
                eligible_sites.append(
                    {
                        'id': str(sc.id),
                        'site_census_id': sc.id,
                        'name': sc.site.site_name,
                        'operator_type': sc.operator_type or '',
                        'address': address,
                    }
                )

            eligible_count = len(eligible_sites)
            eligible_excess = min(excess, eligible_count)

            adjacent_with_shortfalls = []
            for nb in neighbors_for_reallocation(comm, census_year):
                nb_calc = ComplianceCalculation.objects.filter(
                    community=nb,
                    census_year=census_year,
                    program=program,
                ).first()
                shortfall = (nb_calc.shortfall if nb_calc else 0) or 0
                if shortfall <= 0:
                    continue

                pair_re = realloc_by_pair.get((comm.id, nb.id), [])
                reallocations = [
                    {
                        'id': str(r.id),
                        'site_census_id': r.site_census_data_id,
                        'site_name': r.site_census_data.site.site_name,
                        'reallocated_at': r.reallocated_at.isoformat(),
                    }
                    for r in pair_re
                ]

                adjacent_with_shortfalls.append(
                    {
                        'id': str(nb.id),
                        'name': nb.name,
                        'shortfall': shortfall,
                        'reallocations': reallocations,
                        'total_reallocated': len(reallocations),
                    }
                )

            rows.append(
                {
                    'id': str(comm.id),
                    'name': comm.name,
                    'eligible_excess': eligible_excess,
                    'eligible_sites': eligible_sites,
                    'adjacent_with_shortfalls': adjacent_with_shortfalls,
                    '_sort_eligible_excess': eligible_excess,
                    '_sort_adjacent_shortfalls': len(adjacent_with_shortfalls),
                }
            )

        reverse = False
        order_key = ordering or 'name'
        if order_key.startswith('-'):
            reverse = True
            order_key = order_key[1:]

        if order_key == 'eligible_excess':
            rows.sort(key=lambda r: r['_sort_eligible_excess'], reverse=reverse)
        elif order_key == 'adjacent_shortfalls':
            rows.sort(key=lambda r: r['_sort_adjacent_shortfalls'], reverse=reverse)
        else:
            rows.sort(key=lambda r: r['name'].lower(), reverse=reverse)

        for r in rows:
            r.pop('_sort_eligible_excess', None)
            r.pop('_sort_adjacent_shortfalls', None)

        total_docs = len(rows)
        total_eligible_excess = sum(r['eligible_excess'] for r in rows)
        total_adj_shortfalls = sum(
            sum(a['shortfall'] for a in r['adjacent_with_shortfalls']) for r in rows
        )

        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, math.ceil(total_docs / page_size)) if total_docs else 1
        start = (page - 1) * page_size
        page_rows = rows[start : start + page_size]

        return {
            'results': page_rows,
            'communities': page_rows,
            'summary': {
                'communities_with_excess': total_docs,
                'total_eligible_excess': total_eligible_excess,
                'total_adjacent_shortfalls': total_adj_shortfalls,
            },
            'page': page,
            'page_size': page_size,
            'totalPages': total_pages,
            'totalDocs': total_docs,
        }

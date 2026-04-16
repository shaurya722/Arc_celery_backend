from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.db.models import F, Exists, OuterRef, Q, Sum, Avg
from community.models import (
    Community,
    CensusYear,
    CommunityCensusData,
    AdjacentCommunity,
)
from .models import ComplianceCalculation
from .serializers import ComplianceCalculationSerializer
from .tasks import calculate_community_compliance


def _resolve_adjacent_allocation_census_year(census_year_id, year_value):
    """
    Census-year resolution for adjacent-allocation APIs (explicit id or calendar year).
    Returns (CensusYear instance, None) or (None, dict with 'error' and 'status' for Response).
    """
    if census_year_id not in (None, ''):
        try:
            return CensusYear.objects.get(id=census_year_id), None
        except (CensusYear.DoesNotExist, ValueError, TypeError):
            return None, {'error': f'Census year id {census_year_id} not found.', 'status': status.HTTP_404_NOT_FOUND}
    if year_value not in (None, ''):
        try:
            return CensusYear.objects.get(year=int(year_value)), None
        except (CensusYear.DoesNotExist, ValueError, TypeError):
            return None, {'error': f'Census year {year_value!r} not found.', 'status': status.HTTP_404_NOT_FOUND}
    return None, {
        'error': 'census_year_id or year is required (scope adjacent allocations to one census year).',
        'hint': 'Use census_year_id (pk) or year (calendar year), e.g. ?census_year_id=13 or ?year=2050.',
        'status': status.HTTP_400_BAD_REQUEST,
    }


def _sync_recalculate_compliance(community_ids, census_year, program):
    """
    Synchronously recalculate and persist ComplianceCalculation for the given
    community IDs / census_year / program so that subsequent reads see up-to-date numbers.
    """
    from .utils import calculate_compliance

    for cid in community_ids:
        if not cid:
            continue
        try:
            community = Community.objects.get(id=cid)
        except Community.DoesNotExist:
            continue
        metrics = calculate_compliance(community, program, census_year)
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
                'created_by': None,
            },
        )


class ComplianceCalculationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


class ComplianceCalculationListCreate(APIView):
    """
    List all compliance calculations or trigger a new calculation.
    """
    pagination_class = ComplianceCalculationPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['community', 'program', 'created_at', 'census_year', 'shortfall', 'excess', 'compliance_rate']
    search_fields = ['community__name', 'program', 'census_year__year']
    ordering_fields = ['created_at', 'compliance_rate', 'shortfall', 'excess', 'required_sites', 'actual_sites', 'community__name', 'census_year__year', 'program']
    
    def get(self, request):
        from community.models import CommunityCensusData
        
        # Start with all compliance records
        calculations = ComplianceCalculation.objects.all().select_related('community', 'census_year', 'created_by')
        
        # Exclude compliance records for communities that are inactive in their census year
        inactive_community_census = CommunityCensusData.objects.filter(is_active=False)
        
        # Create exclude filter for inactive combinations
        exclude_filters = Q()
        for census_data in inactive_community_census:
            exclude_filters |= Q(
                community_id=census_data.community_id,
                census_year_id=census_data.census_year_id
            )
        
        if exclude_filters:
            calculations = calculations.exclude(exclude_filters)
        
        # Apply user filters
        program = request.query_params.get('program')
        community = request.query_params.get('community')
        census_year = request.query_params.get('census_year')
        year = request.query_params.get('year')
        status_filter = request.query_params.get('status')
        search = request.query_params.get('search')
        
        if search:
            calculations = calculations.filter(
                Q(community__name__icontains=search) |
                Q(program__icontains=search) |
                Q(census_year__year__icontains=search)
            )
        if program:
            calculations = calculations.filter(program=program)
        if community:
            calculations = calculations.filter(community__id=community)
        if census_year:
            calculations = calculations.filter(census_year__id=census_year)
        if year:
            calculations = calculations.filter(census_year__year=year)
        if status_filter:
            if status_filter == 'compliant':
                calculations = calculations.filter(shortfall=0, excess=0)
            elif status_filter == 'shortfall':
                calculations = calculations.filter(shortfall__gt=0)
            elif status_filter == 'excess':
                calculations = calculations.filter(excess__gt=0)
        
        # Compute summary aggregates
        compliant_communities = calculations.filter(shortfall=0, excess=0).count()
        total_shortfall = calculations.aggregate(total=Sum('shortfall'))['total'] or 0
        total_excess = calculations.aggregate(total=Sum('excess'))['total'] or 0
        overall_rate = calculations.aggregate(avg=Avg('compliance_rate'))['avg'] or 0
        total_sites = calculations.aggregate(total=Sum('actual_sites'))['total'] or 0
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        calculations = calculations.order_by(ordering)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(calculations, request)
        
        if page is not None:
            serializer = ComplianceCalculationSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data).data
            response_data['summary'] = {
                'compliant_communities': compliant_communities,
                'shortfalls': total_shortfall,
                'excesses': total_excess,
                'overall_rate': round(overall_rate, 2) if overall_rate else 0,
                'total_sites': total_sites
            }
            return Response(response_data)
        
        serializer = ComplianceCalculationSerializer(calculations, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """
        Trigger compliance calculation for a specific community and census year.
        """
        community_id = request.data.get('community')
        program = request.data.get('program')
        census_year_id = request.data.get('census_year')
        
        if not community_id:
            return Response(
                {'error': 'community field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that the community exists
        try:
            from community.models import Community, CensusYear
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {'error': 'Community not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get census year
        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=census_year_id)
            except CensusYear.DoesNotExist:
                return Response(
                    {'error': 'Census year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get the latest census year for this community
            latest_census_data = community.census_data.order_by('-census_year__year').first()
            if latest_census_data:
                census_year = latest_census_data.census_year
            else:
                return Response(
                    {'error': 'No census data found for this community'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Trigger async calculation (will create zero values if community is inactive)
        task = calculate_community_compliance.delay(
            str(community_id),
            program=program,
            census_year_id=census_year.id,
        )

        return Response({
            'message': 'Compliance calculation triggered',
            'task_id': task.id,
            'community': community_id,
            'program': program or 'all',
            'census_year': census_year.id,
            'census_year_calendar': census_year.year,
        }, status=status.HTTP_202_ACCEPTED)


class ComplianceCalculationDetail(APIView):
    """
    Retrieve or delete a compliance calculation.
    """
    def get_object(self, pk):
        try:
            return ComplianceCalculation.objects.select_related('community', 'census_year', 'created_by').get(pk=pk)
        except ComplianceCalculation.DoesNotExist:
            return None
    
    def get(self, request, pk):
        calculation = self.get_object(pk)
        if calculation is None:
            return Response(
                {'error': 'Compliance calculation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ComplianceCalculationSerializer(calculation)
        return Response(serializer.data)
    
    def delete(self, request, pk):
        calculation = self.get_object(pk)
        if calculation is None:
            return Response(
                {'error': 'Compliance calculation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        calculation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManualComplianceRecalculation(APIView):
    """
    POST: Full compliance recalculation for every community that has data in a census year.
    Runs **synchronously** so the response contains the final numbers (no stale-worker issues).

    Body / query: census_year or census_year_id (integer PK) or year (calendar year).
    If omitted, uses latest census year.
    """

    def post(self, request):
        from .utils import calculate_compliance
        from sites.models import SiteCensusData, SiteReallocation

        census_year_id = (
            request.data.get('census_year')
            or request.data.get('census_year_id')
            or request.query_params.get('census_year')
            or request.query_params.get('census_year_id')
        )
        year_value = request.data.get('year') or request.query_params.get('year')

        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=int(census_year_id))
            except (CensusYear.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'error': f'Census year id {census_year_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif year_value:
            try:
                census_year = CensusYear.objects.get(year=int(year_value))
            except (CensusYear.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'error': f'Census year {year_value} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            census_year = CensusYear.objects.order_by('-year').first()
            if not census_year:
                return Response(
                    {'error': 'No census year in the system.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        programs = ['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']

        # Gather every community that has census data, compliance data, sites, or reallocations
        community_ids = set(
            CommunityCensusData.objects.filter(census_year=census_year)
            .values_list('community_id', flat=True)
        )
        community_ids |= set(
            ComplianceCalculation.objects.filter(census_year=census_year)
            .values_list('community_id', flat=True)
        )
        community_ids |= set(
            SiteCensusData.objects.filter(census_year=census_year, is_active=True)
            .exclude(community__isnull=True)
            .values_list('community_id', flat=True)
        )
        community_ids |= set(
            SiteReallocation.objects.filter(census_year=census_year)
            .values_list('from_community_id', flat=True)
        )
        community_ids |= set(
            SiteReallocation.objects.filter(census_year=census_year)
            .values_list('to_community_id', flat=True)
        )

        communities = Community.objects.filter(id__in=community_ids).order_by('name')

        results = []
        for community in communities:
            community_results = {
                'community_id': str(community.id),
                'community_name': community.name,
                'programs': {},
            }
            for program in programs:
                metrics = calculate_compliance(community, program, census_year)
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
                        'created_by': None,
                    },
                )
                community_results['programs'][program] = metrics
            results.append(community_results)

        total_communities = len(results)
        shortfall_communities = sum(
            1 for r in results if any(p['shortfall'] > 0 for p in r['programs'].values())
        )
        excess_communities = sum(
            1 for r in results if any(p['excess'] > 0 for p in r['programs'].values())
        )

        return Response({
            'message': f'Compliance recalculated for {total_communities} communities.',
            'census_year': {'id': census_year.id, 'year': census_year.year},
            'total_communities': total_communities,
            'communities_with_shortfall': shortfall_communities,
            'communities_with_excess': excess_communities,
            'results': results,
        }, status=status.HTTP_200_OK)


class AdjacentAllocationListView(APIView):
    """
    GET: Communities that have active census data for a given census year, with adjacent
    neighbors, per-program shortfall/excess, eligible sites and reallocations for that year.

    Required query params: program, and one of census_year_id or year.
    """

    def get(self, request):
        import math
        from collections import defaultdict
        from sites.models import SiteCensusData, SiteReallocation
        from sites.adjacent_reallocation import (
            PROGRAM_FIELD,
            neighbors_for_reallocation,
            reallocation_cap_status,
        )

        program = request.query_params.get('program')
        census_year_id = request.query_params.get('census_year_id')
        year_value = request.query_params.get('year')
        search = request.query_params.get('search')
        ordering = request.query_params.get('ordering', 'name')
        try:
            page = int(request.query_params.get('page', 1))
        except (TypeError, ValueError):
            page = 1
        try:
            limit = int(request.query_params.get('limit', 20))
        except (TypeError, ValueError):
            limit = 20

        if not program:
            return Response(
                {'error': 'program query parameter is required (Paint, Lighting, Solvents, Pesticides, Fertilizers).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if program not in PROGRAM_FIELD:
            return Response(
                {'error': f'Invalid program {program!r}. Expected one of {list(PROGRAM_FIELD)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        census_year, cy_err = _resolve_adjacent_allocation_census_year(census_year_id, year_value)
        if cy_err:
            err_body = {'error': cy_err['error']}
            if cy_err.get('hint'):
                err_body['hint'] = cy_err['hint']
            return Response(err_body, status=cy_err['status'])

        field = PROGRAM_FIELD[program]
        non_reallocatable_ops = ['Municipal', 'First Nation/Indigenous', 'Regional District']

        # Communities that have compliance data, active census data, or reallocations
        # for this census year + program — so we never silently drop communities.
        community_ids_from_compliance = set(
            ComplianceCalculation.objects.filter(census_year=census_year, program=program)
            .values_list('community_id', flat=True)
        )
        community_ids_from_census = set(
            CommunityCensusData.objects.filter(census_year=census_year)
            .values_list('community_id', flat=True)
        )
        community_ids_from_realloc = set()
        realloc_qs = SiteReallocation.objects.filter(
            census_year=census_year,
            **{f'site_census_data__{field}': True},
        ).select_related('site_census_data__site', 'from_community', 'to_community')
        for r in realloc_qs:
            community_ids_from_realloc.add(r.from_community_id)
            community_ids_from_realloc.add(r.to_community_id)

        relevant_ids = community_ids_from_compliance | community_ids_from_census | community_ids_from_realloc

        communities_qs = Community.objects.filter(id__in=relevant_ids).order_by('name')
        if search and str(search).strip():
            communities_qs = communities_qs.filter(name__icontains=str(search).strip())

        compliance_map = {}
        for calc in ComplianceCalculation.objects.filter(
            census_year=census_year, program=program
        ).select_related('community'):
            compliance_map[calc.community_id] = calc

        realloc_from = defaultdict(lambda: defaultdict(list))
        realloc_to = defaultdict(lambda: defaultdict(list))
        for r in realloc_qs:
            realloc_from[r.from_community_id][r.to_community_id].append(r)
            realloc_to[r.to_community_id][r.from_community_id].append(r)

        def _realloc_detail(r):
            return {
                'id': str(r.id),
                'site_census_id': r.site_census_data_id,
                'site_name': r.site_census_data.site.site_name,
                'from_community': r.from_community.name,
                'from_community_id': str(r.from_community_id),
                'to_community': r.to_community.name,
                'to_community_id': str(r.to_community_id),
                'reallocated_at': r.reallocated_at.isoformat(),
                'reason': r.reason or '',
            }

        rows = []
        for comm in communities_qs:
            calc = compliance_map.get(comm.id)
            shortfall = (calc.shortfall if calc else 0) or 0
            excess = (calc.excess if calc else 0) or 0
            required = (calc.required_sites if calc else 0) or 0
            actual = (calc.actual_sites if calc else 0) or 0

            eligible_sites = []
            if excess > 0:
                eligible_qs = SiteCensusData.objects.filter(
                    community=comm,
                    census_year=census_year,
                    is_active=True,
                    **{field: True},
                ).exclude(site_type='Event').exclude(
                    operator_type__in=non_reallocatable_ops,
                ).select_related('site')
                for sc in eligible_qs:
                    addr_parts = [sc.address_line_1, sc.address_city, sc.address_postal_code]
                    eligible_sites.append({
                        'id': str(sc.id),
                        'site_census_id': sc.id,
                        'name': sc.site.site_name,
                        'operator_type': sc.operator_type or '',
                        'address': ', '.join(p for p in addr_parts if p),
                    })

            neighbors = neighbors_for_reallocation(comm, census_year)
            adjacent_communities = []
            for nb in neighbors:
                nb_calc = compliance_map.get(nb.id)
                nb_shortfall = (nb_calc.shortfall if nb_calc else 0) or 0
                nb_excess = (nb_calc.excess if nb_calc else 0) or 0
                nb_required = (nb_calc.required_sites if nb_calc else 0) or 0
                nb_actual = (nb_calc.actual_sites if nb_calc else 0) or 0

                outgoing = realloc_from.get(comm.id, {}).get(nb.id, [])
                incoming = realloc_to.get(comm.id, {}).get(nb.id, [])
                cap = reallocation_cap_status(nb, census_year, program, nb_required)

                adjacent_communities.append({
                    'id': str(nb.id),
                    'name': nb.name,
                    'shortfall': nb_shortfall,
                    'excess': nb_excess,
                    'required': nb_required,
                    'actual': nb_actual,
                    'reallocation_cap': cap,
                    'allocated_to': [_realloc_detail(r) for r in outgoing],
                    'allocated_from': [_realloc_detail(r) for r in incoming],
                    'total_allocated_to': len(outgoing),
                    'total_allocated_from': len(incoming),
                })

            # Flat summary of all allocated sites from this community
            all_outgoing = []
            for nb_id, r_list in realloc_from.get(comm.id, {}).items():
                for r in r_list:
                    all_outgoing.append(_realloc_detail(r))
            all_incoming = []
            for nb_id, r_list in realloc_to.get(comm.id, {}).items():
                for r in r_list:
                    all_incoming.append(_realloc_detail(r))

            total_allocated_out = len(all_outgoing)
            total_allocated_in = len(all_incoming)

            rows.append({
                'id': str(comm.id),
                'name': comm.name,
                'required': required,
                'actual': actual,
                'shortfall': shortfall,
                'excess': excess,
                'eligible_excess': min(excess, len(eligible_sites)),
                'eligible_sites': eligible_sites,
                'adjacent_communities': adjacent_communities,
                'adjacent_count': len(adjacent_communities),
                'allocated_out': all_outgoing,
                'allocated_in': all_incoming,
                'total_allocated_out': total_allocated_out,
                'total_allocated_in': total_allocated_in,
                '_sort_shortfall': shortfall,
                '_sort_excess': excess,
            })

        reverse = False
        order_key = ordering or 'name'
        if order_key.startswith('-'):
            reverse = True
            order_key = order_key[1:]

        sort_map = {
            'shortfall': '_sort_shortfall',
            'excess': '_sort_excess',
            'required': 'required',
            'actual': 'actual',
        }
        if order_key in sort_map:
            rows.sort(key=lambda r: r.get(sort_map[order_key], 0), reverse=reverse)
        else:
            rows.sort(key=lambda r: r['name'].lower(), reverse=reverse)

        for r in rows:
            r.pop('_sort_shortfall', None)
            r.pop('_sort_excess', None)

        total_docs = len(rows)
        total_shortfall_sum = sum(r['shortfall'] for r in rows)
        total_excess_sum = sum(r['excess'] for r in rows)
        communities_with_shortfall = sum(1 for r in rows if r['shortfall'] > 0)
        communities_with_excess = sum(1 for r in rows if r['excess'] > 0)

        page = max(1, page)
        limit = max(1, min(limit, 200))
        total_pages = max(1, math.ceil(total_docs / limit)) if total_docs else 1
        start = (page - 1) * limit
        page_rows = rows[start:start + limit]

        return Response({
            'results': page_rows,
            'summary': {
                'total_communities': total_docs,
                'communities_with_shortfall': communities_with_shortfall,
                'communities_with_excess': communities_with_excess,
                'total_shortfall': total_shortfall_sum,
                'total_excess': total_excess_sum,
            },
            'census_year': {'id': census_year.id, 'year': census_year.year},
            'program': program,
            'page': page,
            'page_size': limit,
            'totalPages': total_pages,
            'totalDocs': total_docs,
        }, status=status.HTTP_200_OK)


class AdjacentAllocationDetailView(APIView):
    """
    GET /api/compliance/adjacent-allocations/<uuid:pk>/
    Return a single SiteReallocation with from/to community details, compliance
    snapshots, and the allocated site info.
    """

    def get(self, request, pk):
        from sites.models import SiteReallocation, SiteCensusData
        from .utils import calculate_compliance

        try:
            realloc = SiteReallocation.objects.select_related(
                'site_census_data__site',
                'site_census_data__community',
                'site_census_data__census_year',
                'from_community',
                'to_community',
                'census_year',
                'created_by',
            ).get(id=pk)
        except SiteReallocation.DoesNotExist:
            return Response(
                {'error': f'Reallocation {pk} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        sc = realloc.site_census_data
        addr_parts = [sc.address_line_1, sc.address_city, sc.address_postal_code]

        program = realloc.reason or ''
        program_field_map = {
            'Paint': 'program_paint',
            'Lighting': 'program_lights',
            'Solvents': 'program_solvents',
            'Pesticides': 'program_pesticides',
            'Fertilizers': 'program_fertilizers',
        }
        detected_program = None
        for prog, field in program_field_map.items():
            if getattr(sc, field, False):
                detected_program = prog
                break

        all_reallocs_for_site = SiteReallocation.objects.filter(
            site_census_data=sc,
        ).select_related('from_community', 'to_community', 'created_by').order_by('-reallocated_at')

        history = []
        for r in all_reallocs_for_site:
            history.append({
                'id': str(r.id),
                'from_community': r.from_community.name,
                'from_community_id': str(r.from_community_id),
                'to_community': r.to_community.name,
                'to_community_id': str(r.to_community_id),
                'reallocated_at': r.reallocated_at.isoformat(),
                'reason': r.reason or '',
                'created_by': str(r.created_by) if r.created_by else None,
            })

        from_comp = realloc.from_community
        to_comp = realloc.to_community
        cy = realloc.census_year

        def _compliance_snapshot(community):
            calc = ComplianceCalculation.objects.filter(
                community=community, census_year=cy,
            ).first()
            if detected_program:
                calc = ComplianceCalculation.objects.filter(
                    community=community, census_year=cy, program=detected_program,
                ).first()
            if calc:
                return {
                    'required': calc.required_sites,
                    'actual': calc.actual_sites,
                    'shortfall': calc.shortfall,
                    'excess': calc.excess,
                    'compliance_rate': float(calc.compliance_rate or 0),
                    'program': calc.program,
                }
            return None

        return Response({
            'id': str(realloc.id),
            'site_census_id': sc.id,
            'site_name': sc.site.site_name,
            'site_type': sc.site_type or '',
            'operator_type': sc.operator_type or '',
            'address': ', '.join(p for p in addr_parts if p),
            'program': detected_program,
            'from_community': {
                'id': str(from_comp.id),
                'name': from_comp.name,
                'compliance': _compliance_snapshot(from_comp),
            },
            'to_community': {
                'id': str(to_comp.id),
                'name': to_comp.name,
                'compliance': _compliance_snapshot(to_comp),
            },
            'census_year': {'id': cy.id, 'year': cy.year},
            'reallocated_at': realloc.reallocated_at.isoformat(),
            'reason': realloc.reason or '',
            'created_by': str(realloc.created_by) if realloc.created_by else None,
            'reallocation_history': history,
        }, status=status.HTTP_200_OK)


class AdjacentAllocationCreateUpdateView(APIView):
    """
    POST: Allocate site(s) to an adjacent community; every SiteCensusData row must match
    the census year (census_year_id or year in JSON body or query string).

    PATCH: Move an existing SiteReallocation to a new target; census year must match
    the reallocation record (census_year_id or year in body or query).
    """

    def post(self, request):
        """
        Allocate one or more sites to an adjacent community with shortfall.

        Body:
        {
            "site_census_ids": [123, 456],       // list of SiteCensusData PKs
            "to_community_id": "<uuid>",
            "program": "Paint",
            "census_year_id": 13,                 // optional; inferred from first site if omitted
            "reason": "Adjacent reallocation"     // optional
        }
        """
        from sites.services import SiteReallocationService
        from sites.models import SiteCensusData
        from django.core.exceptions import ValidationError as DjangoValidationError

        site_census_ids = request.data.get('site_census_ids', [])
        to_community_id = request.data.get('to_community_id')
        program = request.data.get('program')
        reason = request.data.get('reason', '')
        body_cy_id = request.data.get('census_year_id') or request.query_params.get('census_year_id')
        body_year = request.data.get('year') if request.data.get('year') is not None else request.query_params.get('year')

        if not site_census_ids:
            return Response({'error': 'site_census_ids is required (list of SiteCensusData PKs).'}, status=status.HTTP_400_BAD_REQUEST)
        if not to_community_id:
            return Response({'error': 'to_community_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not program:
            return Response({'error': 'program is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Census year: explicit in body/query, or inferred from the first site
        census_year = None
        if body_cy_id not in (None, '') or body_year not in (None, ''):
            census_year, cy_err = _resolve_adjacent_allocation_census_year(body_cy_id, body_year)
            if cy_err:
                err_body = {'error': cy_err['error']}
                if cy_err.get('hint'):
                    err_body['hint'] = cy_err['hint']
                return Response(err_body, status=cy_err['status'])

        try:
            to_community = Community.objects.get(id=to_community_id)
        except Community.DoesNotExist:
            return Response({'error': f'Community {to_community_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

        results = []
        errors = []
        user = request.user if request.user.is_authenticated else None

        for sc_id in site_census_ids:
            try:
                sc = SiteCensusData.objects.select_related('site', 'community', 'census_year').get(id=sc_id)
            except SiteCensusData.DoesNotExist:
                errors.append({'site_census_id': sc_id, 'error': f'SiteCensusData {sc_id} not found.'})
                continue

            # Infer census_year from first valid site if not explicitly provided
            if census_year is None:
                census_year = sc.census_year

            if sc.census_year_id != census_year.id:
                errors.append({
                    'site_census_id': sc_id,
                    'error': (
                        f'Site census row is for census year {sc.census_year.year} (id={sc.census_year_id}); '
                        f'request targets {census_year.year} (id={census_year.id}).'
                    ),
                })
                continue

            try:
                reallocation = SiteReallocationService.reallocate(
                    site_census_data=sc,
                    to_community=to_community,
                    user=user,
                    reason=reason,
                    program=program,
                )
                results.append({
                    'id': str(reallocation.id),
                    'site_census_id': sc.id,
                    'site_name': sc.site.site_name,
                    'source_community': reallocation.from_community.name,
                    'source_community_id': str(reallocation.from_community_id),
                    'target_community': reallocation.to_community.name,
                    'target_community_id': str(reallocation.to_community_id),
                    'from_community': reallocation.from_community.name,
                    'from_community_id': str(reallocation.from_community_id),
                    'to_community': reallocation.to_community.name,
                    'to_community_id': str(reallocation.to_community_id),
                    'reallocated_at': reallocation.reallocated_at.isoformat(),
                    'reason': reason or '',
                })
            except DjangoValidationError as e:
                errors.append({'site_census_id': sc_id, 'error': str(e)})

        # Recalculate compliance synchronously for all affected communities
        if results and census_year:
            affected_ids = {str(to_community.id)}
            for r in results:
                fid = r.get('from_community_id')
                if fid:
                    affected_ids.add(fid)
            _sync_recalculate_compliance(affected_ids, census_year, program)

        resp_status = status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST
        resp_data = {
            'program': program,
            'allocated': results,
            'errors': errors,
            'total_allocated': len(results),
            'total_errors': len(errors),
        }
        if census_year:
            resp_data['census_year'] = {'id': census_year.id, 'year': census_year.year}
        return Response(resp_data, status=resp_status)

    def patch(self, request):
        """
        Update an existing allocation: undo the old reallocation and create a new one
        to a different target community.

        Body:
        {
            "reallocation_id": "<uuid>",          // existing SiteReallocation PK
            "new_to_community_id": "<uuid>",      // new target community
            "program": "Paint",
            "census_year_id": 13,                 // optional; inferred from reallocation if omitted
            "reason": "Corrected adjacent allocation"  // optional
        }
        """
        from sites.services import SiteReallocationService
        from sites.models import SiteReallocation as SR
        from django.core.exceptions import ValidationError as DjangoValidationError

        reallocation_id = request.data.get('reallocation_id')
        new_to_community_id = request.data.get('new_to_community_id')
        program = request.data.get('program')
        reason = request.data.get('reason', '')
        body_cy_id = request.data.get('census_year_id') or request.query_params.get('census_year_id')
        body_year = request.data.get('year') if request.data.get('year') is not None else request.query_params.get('year')

        if not reallocation_id:
            return Response({'error': 'reallocation_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not new_to_community_id:
            return Response({'error': 'new_to_community_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not program:
            return Response({'error': 'program is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            old_realloc = SR.objects.select_related(
                'site_census_data__site', 'site_census_data__community',
                'site_census_data__census_year', 'from_community', 'to_community',
            ).get(id=reallocation_id)
        except SR.DoesNotExist:
            return Response({'error': f'Reallocation {reallocation_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Census year: explicit in body/query, or inferred from the reallocation record
        census_year = None
        if body_cy_id not in (None, '') or body_year not in (None, ''):
            census_year, cy_err = _resolve_adjacent_allocation_census_year(body_cy_id, body_year)
            if cy_err:
                err_body = {'error': cy_err['error']}
                if cy_err.get('hint'):
                    err_body['hint'] = cy_err['hint']
                return Response(err_body, status=cy_err['status'])
            if old_realloc.census_year_id != census_year.id:
                return Response(
                    {
                        'error': (
                            f'Reallocation belongs to census year id={old_realloc.census_year_id} '
                            f'({old_realloc.census_year.year}); request targets id={census_year.id} ({census_year.year}).'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            census_year = old_realloc.census_year

        try:
            new_to_community = Community.objects.get(id=new_to_community_id)
        except Community.DoesNotExist:
            return Response({'error': f'Community {new_to_community_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        site_census_data = old_realloc.site_census_data
        old_from_community_id = old_realloc.from_community_id
        old_to_community_id = old_realloc.to_community_id

        try:
            SiteReallocationService.undo_reallocation(reallocation_id=reallocation_id, user=user)
        except DjangoValidationError as e:
            return Response({'error': f'Failed to undo existing allocation: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_realloc = SiteReallocationService.reallocate(
                site_census_data=site_census_data,
                to_community=new_to_community,
                user=user,
                reason=reason or f'Updated from {old_realloc.to_community.name} to {new_to_community.name}',
                program=program,
            )
        except DjangoValidationError as e:
            return Response({
                'error': f'Undo succeeded but new allocation failed: {e}',
                'hint': 'The old allocation was undone; create a new one manually if needed.',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Recalculate compliance synchronously for all affected communities
        affected_ids = {
            str(old_from_community_id),
            str(old_to_community_id),
            str(new_to_community.id),
            str(site_census_data.community_id),
        }
        _sync_recalculate_compliance(affected_ids, census_year, program)

        return Response({
            'message': 'Allocation updated successfully.',
            'census_year': {'id': census_year.id, 'year': census_year.year},
            'program': program,
            'old_reallocation_id': str(reallocation_id),
            'new_reallocation': {
                'id': str(new_realloc.id),
                'site_census_id': site_census_data.id,
                'site_name': site_census_data.site.site_name,
                'from_community': new_realloc.from_community.name,
                'to_community': new_realloc.to_community.name,
                'reallocated_at': new_realloc.reallocated_at.isoformat(),
            },
        }, status=status.HTTP_200_OK)

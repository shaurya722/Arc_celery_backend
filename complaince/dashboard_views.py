"""
Aggregated JSON for the compliance dashboard charts (KPIs, donuts, bars, trends).
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Exists, OuterRef, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from community.models import CensusYear, CommunityCensusData
from sites.models import SiteCensusData

from .models import ComplianceCalculation
from .views import AuthenticatedAPIView

STANDARD_PROGRAMS = ('Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers')

# Frontend palette (GovCompliance-style); client may ignore and use CSS tokens.
CHART_COLORS = {
    'navy': '#1e3a8a',
    'royal': '#2563eb',
    'light_blue': '#93c5fd',
    'sky_fill': '#dbeafe',
}


def _inactive_ccd_exists():
    return Exists(
        CommunityCensusData.objects.filter(
            is_active=False,
            community_id=OuterRef('community_id'),
            census_year_id=OuterRef('census_year_id'),
        )
    )


def _calculations_qs_for_year(census_year: CensusYear):
    return (
        ComplianceCalculation.objects.filter(census_year=census_year)
        .annotate(_inactive=_inactive_ccd_exists())
        .filter(_inactive=False)
        .select_related('community')
    )


def _resolve_dashboard_census_year(request):
    """Returns (CensusYear | None, error_response | None)."""
    census_year_id = (
        request.query_params.get('census_year_id')
        or request.query_params.get('census_year')
    )
    year_value = request.query_params.get('year')
    if census_year_id not in (None, ''):
        try:
            return CensusYear.objects.get(id=int(census_year_id)), None
        except (CensusYear.DoesNotExist, ValueError, TypeError):
            return None, Response(
                {'error': f'Census year id {census_year_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
    if year_value not in (None, ''):
        try:
            return CensusYear.objects.get(year=int(year_value)), None
        except (CensusYear.DoesNotExist, ValueError, TypeError):
            return None, Response(
                {'error': f'Census year {year_value!r} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
    cy = CensusYear.objects.order_by('-year').first()
    if not cy:
        return None, Response(
            {'error': 'No census year in the system.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return cy, None


def _relative_time(dt):
    if not dt:
        return ''
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return 'soon'
    if secs < 3600:
        return f'{max(1, secs // 60)}m ago'
    if secs < 86400:
        return f'{secs // 3600}h ago'
    if secs < 86400 * 2:
        return 'Yesterday'
    return dt.strftime('%b %d')


class ComplianceDashboardGraphView(AuthenticatedAPIView):
    """
    GET /api/compliance/dashboard/graph/

    Query params:
    - census_year_id or year: scope calculations and site counts (default: latest census year)
    - exclude_events: true|false — exclude Event rows from site KPI and top communities (default: false)
    - top_communities_limit: default 8
    - sites_table_limit: default 10

    Response shapes align with the Next.js ComplianceDashboardStatic charts:
    KPI strip, donut, program bar chart, top communities, end-date buckets, activity-style rows.
    """

    def get(self, request):
        census_year, err = _resolve_dashboard_census_year(request)
        if err:
            return err

        exclude_events = str(request.query_params.get('exclude_events', 'false')).lower() in (
            '1',
            'true',
            'yes',
        )
        try:
            top_n = max(1, min(int(request.query_params.get('top_communities_limit', 8)), 50))
        except (TypeError, ValueError):
            top_n = 8
        try:
            table_limit = max(1, min(int(request.query_params.get('sites_table_limit', 10)), 100))
        except (TypeError, ValueError):
            table_limit = 10

        calc_qs = _calculations_qs_for_year(census_year)

        municipalities_tracked = (
            CommunityCensusData.objects.filter(census_year=census_year, is_active=True).aggregate(
                n=Count('community_id', distinct=True)
            )['n']
            or 0
        )

        # --- KPI: total site census rows (collection + events unless excluded)
        site_filter = Q(census_year=census_year, is_active=True)
        if exclude_events:
            site_filter &= ~Q(site_type='Event')
        total_sites = SiteCensusData.objects.filter(site_filter).count()

        # --- Municipality rollup (mutually exclusive donut buckets)
        by_community = {}
        for row in calc_qs.values(
            'community_id',
            'shortfall',
            'excess',
        ):
            cid = row['community_id']
            if cid not in by_community:
                by_community[cid] = {'any_shortfall': False, 'any_excess': False}
            if (row['shortfall'] or 0) > 0:
                by_community[cid]['any_shortfall'] = True
            if (row['excess'] or 0) > 0:
                by_community[cid]['any_excess'] = True

        muni_shortfall = sum(1 for v in by_community.values() if v['any_shortfall'])
        muni_balanced = sum(
            1 for v in by_community.values() if not v['any_shortfall'] and not v['any_excess']
        )
        muni_excess_only = sum(
            1 for v in by_community.values() if not v['any_shortfall'] and v['any_excess']
        )
        muni_any_excess = sum(1 for v in by_community.values() if v['any_excess'])
        municipalities_in_calc = len(by_community)
        municipalities_compliant_no_shortfall = municipalities_in_calc - muni_shortfall

        overall_rate_row = calc_qs.aggregate(avg=Avg('compliance_rate'))
        overall_rate = round(float(overall_rate_row['avg'] or 0), 2)

        agg_sums = calc_qs.aggregate(
            sum_shortfall=Sum('shortfall'),
            sum_excess=Sum('excess'),
        )
        total_shortfall_units = int(agg_sums['sum_shortfall'] or 0)
        total_excess_units = int(agg_sums['sum_excess'] or 0)

        compliance_rate_municipalities_pct = (
            round(100.0 * municipalities_compliant_no_shortfall / municipalities_in_calc, 2)
            if municipalities_in_calc
            else 0.0
        )

        kpi = {
            'total_sites': total_sites,
            'municipalities_tracked': municipalities_tracked,
            'municipalities_with_calculations': municipalities_in_calc,
            'compliance_rate_avg_program_rows': overall_rate,
            'compliance_rate_municipalities_pct': compliance_rate_municipalities_pct,
            'municipalities_compliant_no_shortfall': municipalities_compliant_no_shortfall,
            'municipalities_with_shortfall': muni_shortfall,
            'municipalities_balanced': muni_balanced,
            'municipalities_excess_only': muni_excess_only,
            'municipalities_with_any_excess': muni_any_excess,
            'total_shortfall_units': total_shortfall_units,
            'total_excess_units': total_excess_units,
        }

        donut = [
            {'name': 'Compliant', 'value': muni_balanced, 'fill': CHART_COLORS['navy']},
            {'name': 'Shortfall', 'value': muni_shortfall, 'fill': CHART_COLORS['royal']},
            {'name': 'Excess', 'value': muni_excess_only, 'fill': CHART_COLORS['light_blue']},
        ]

        # --- Program bar chart: communities with no shortfall vs with shortfall, per program
        program_compliance = []
        for prog in STANDARD_PROGRAMS:
            qs_p = calc_qs.filter(program=prog)
            compliant_c = qs_p.filter(shortfall=0).values('community_id').distinct().count()
            shortfall_c = qs_p.filter(shortfall__gt=0).values('community_id').distinct().count()
            display = 'Lights' if prog == 'Lighting' else prog
            program_compliance.append(
                {
                    'program': prog,
                    'program_display': display,
                    'compliant_communities': compliant_c,
                    'shortfall_communities': shortfall_c,
                    # Aliases for bar charts matching static mock keys:
                    'compliant': compliant_c,
                    'shortfall': shortfall_c,
                }
            )

        # --- Top communities by active site rows in this census year
        site_comm_qs = (
            SiteCensusData.objects.filter(census_year=census_year, is_active=True)
            .exclude(community__isnull=True)
        )
        if exclude_events:
            site_comm_qs = site_comm_qs.exclude(site_type='Event')
        top_rows = (
            site_comm_qs.values('community_id', 'community__name')
            .annotate(sites=Count('id'))
            .order_by('-sites')[:top_n]
        )
        top_communities = [
            {'name': r['community__name'] or '', 'sites': r['sites']} for r in top_rows
        ]

        # --- End-date buckets (site_end_date vs today)
        now = timezone.now()
        horizon_far = now + timedelta(days=365 * 5)
        ending_qs = SiteCensusData.objects.filter(
            census_year=census_year,
            is_active=True,
            site_end_date__isnull=False,
            site_end_date__gte=now,
            site_end_date__lte=horizon_far,
        ).exclude(community__isnull=True)
        if exclude_events:
            ending_qs = ending_qs.exclude(site_type='Event')

        def bucket_for(delta_days):
            if delta_days <= 30:
                return 'lte_30'
            if delta_days <= 60:
                return '31_60'
            if delta_days <= 90:
                return '61_90'
            return 'gt_90'

        bucket_counts = {'lte_30': 0, '31_60': 0, '61_90': 0, 'gt_90': 0}
        for sc in ending_qs.only('site_end_date'):
            delta = (sc.site_end_date - now).days
            bucket_counts[bucket_for(delta)] += 1

        total_bucketed = sum(bucket_counts.values()) or 1
        end_date_buckets = [
            {
                'label': '≤ 30 days',
                'key': 'lte_30',
                'count': bucket_counts['lte_30'],
                'pct': round(100 * bucket_counts['lte_30'] / total_bucketed, 1),
                'fill': '#ef4444',
            },
            {
                'label': '31–60 days',
                'key': '31_60',
                'count': bucket_counts['31_60'],
                'pct': round(100 * bucket_counts['31_60'] / total_bucketed, 1),
                'fill': '#fb923c',
            },
            {
                'label': '61–90 days',
                'key': '61_90',
                'count': bucket_counts['61_90'],
                'pct': round(100 * bucket_counts['61_90'] / total_bucketed, 1),
                'fill': '#38bdf8',
            },
            {
                'label': '90+ days',
                'key': 'gt_90',
                'count': bucket_counts['gt_90'],
                'pct': round(100 * bucket_counts['gt_90'] / total_bucketed, 1),
                'fill': CHART_COLORS['navy'],
            },
        ]
        end_date_bar_chart = [
            {'bucket': b['label'], 'sites': b['count'], 'fill': b['fill']} for b in end_date_buckets
        ]

        # --- Sites ending soon table (nearest site_end_date first)
        PROGRAM_FIELDS = (
            ('Paint', 'program_paint', 'program_paint_end_date'),
            ('Lighting', 'program_lights', 'program_lights_end_date'),
            ('Solvents', 'program_solvents', 'program_solvents_end_date'),
            ('Pesticides', 'program_pesticides', 'program_pesticides_end_date'),
            ('Fertilizers', 'program_fertilizers', 'program_fertilizers_end_date'),
        )

        def primary_program_label(sc: SiteCensusData):
            for label, flag, _end in PROGRAM_FIELDS:
                if getattr(sc, flag, False):
                    disp = 'Lights' if label == 'Lighting' else label
                    return disp
            return '—'

        soon_qs = (
            SiteCensusData.objects.filter(
                census_year=census_year,
                is_active=True,
                site_end_date__isnull=False,
                site_end_date__gte=now,
            )
            .select_related('site', 'community')
            .order_by('site_end_date')[: table_limit * 3]
        )

        activity_rows = []
        seen_keys = set()
        for sc in soon_qs:
            key = (sc.site_id, sc.id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            comm_name = sc.community.name if sc.community else '—'
            sub = f'ID {sc.id} · {comm_name}'
            status_label = 'Active' if sc.is_active else 'Inactive'
            activity_rows.append(
                {
                    'site': sc.site.site_name,
                    'sub': sub,
                    'program': primary_program_label(sc),
                    'status': status_label,
                    'updated': _relative_time(sc.updated_at),
                    'site_end_date': sc.site_end_date.isoformat() if sc.site_end_date else None,
                }
            )
            if len(activity_rows) >= table_limit:
                break

        # --- Trend: real multi-year average compliance (program-row average per census year)
        trend_by_year = []
        for cy in CensusYear.objects.order_by('year'):
            qsy = _calculations_qs_for_year(cy)
            if not qsy.exists():
                continue
            avg_r = qsy.aggregate(avg=Avg('compliance_rate'))['avg']
            trend_by_year.append(
                {
                    'year': cy.year,
                    'census_year_id': cy.id,
                    'rate': round(float(avg_r or 0), 2),
                }
            )

        # Monthly placeholder when single-year dashboard (explicit so UI can label)
        synthetic_monthly = [
            {'month': m, 'rate': overall_rate}
            for m in (
                'Jan',
                'Feb',
                'Mar',
                'Apr',
                'May',
                'Jun',
                'Jul',
                'Aug',
                'Sep',
                'Oct',
                'Nov',
                'Dec',
            )
        ]

        payload = {
            'census_year': {'id': census_year.id, 'year': census_year.year},
            'chart_colors': CHART_COLORS,
            'kpi': kpi,
            'donut': donut,
            'donut_legend': [
                {'name': 'Compliant', 'label': 'Balanced (no shortfall, no excess)', 'count': muni_balanced},
                {'name': 'Shortfall', 'label': 'Any program shortfall', 'count': muni_shortfall},
                {'name': 'Excess', 'label': 'Excess only (no shortfall)', 'count': muni_excess_only},
            ],
            'program_compliance': program_compliance,
            'top_communities': top_communities,
            'end_date_buckets': end_date_buckets,
            'end_date_bar_chart': end_date_bar_chart,
            'sites_ending_soon': activity_rows,
            'trend': {
                'by_census_year': trend_by_year,
                'monthly': synthetic_monthly,
                'monthly_synthetic': True,
                'monthly_note': (
                    'Monthly points repeat the current census year average; '
                    'store monthly snapshots to replace with historical series.'
                ),
            },
            'meta': {
                'exclude_events': exclude_events,
                'programs': list(STANDARD_PROGRAMS),
            },
        }
        return Response(payload)

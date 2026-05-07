from django.urls import path
from .views import (
    ComplianceCalculationListCreate,
    ComplianceCalculationExportView,
    ComplianceCalculationDetail,
    ManualComplianceRecalculation,
    CeleryComplianceRecalculation,
    AdjacentAllocationListView,
    AdjacentAllocationDetailView,
    AdjacentAllocationCreateUpdateView,
)
from .offset_views import (
    DirectServiceOffsetListCreate,
    DirectServiceOffsetDetail,
    DirectServiceOffsetPreview,
    CommunityOffsetListCreate,
    CommunityOffsetDetail,
)
from .report_views import (
    ReportConfigView,
    ReportPreviewView,
    ReportExportView,
)
from .dashboard_views import ComplianceDashboardGraphView

urlpatterns = [
    path('dashboard/graph/', ComplianceDashboardGraphView.as_view(), name='compliance-dashboard-graph'),
    path('export/', ComplianceCalculationExportView.as_view(), name='compliance-export-csv'),
    path('', ComplianceCalculationListCreate.as_view(), name='compliance-list-create'),
    path('<int:pk>/', ComplianceCalculationDetail.as_view(), name='compliance-detail'),
    path('recalculate/', ManualComplianceRecalculation.as_view(), name='manual-recalculate'),
    path('recalculate/celery/', CeleryComplianceRecalculation.as_view(), name='celery-recalculate'),
    path('adjacent-allocations/', AdjacentAllocationListView.as_view(), name='adjacent-allocation-list'),
    path('adjacent-allocations/<uuid:pk>/', AdjacentAllocationDetailView.as_view(), name='adjacent-allocation-detail'),
    path('adjacent-allocations/allocate/', AdjacentAllocationCreateUpdateView.as_view(), name='adjacent-allocation-create-update'),
    # Direct Service Offset (Global) endpoints
    path('direct-service-offsets/', DirectServiceOffsetListCreate.as_view(), name='direct-service-offset-list-create'),
    path('direct-service-offsets/<int:pk>/', DirectServiceOffsetDetail.as_view(), name='direct-service-offset-detail'),
    path('direct-service-offsets/preview/', DirectServiceOffsetPreview.as_view(), name='direct-service-offset-preview'),
    # Community Offset (Per-community override) endpoints
    path('community-offsets/', CommunityOffsetListCreate.as_view(), name='community-offset-list-create'),
    path('community-offsets/<int:pk>/', CommunityOffsetDetail.as_view(), name='community-offset-detail'),
    # Reports (superadmin)
    path('reports/config/', ReportConfigView.as_view(), name='reports-config'),
    path('reports/preview/', ReportPreviewView.as_view(), name='reports-preview'),
    path('reports/export/', ReportExportView.as_view(), name='reports-export'),
]

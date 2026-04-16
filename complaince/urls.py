from django.urls import path
from .views import (
    ComplianceCalculationListCreate,
    ComplianceCalculationDetail,
    ManualComplianceRecalculation,
    AdjacentAllocationListView,
    AdjacentAllocationDetailView,
    AdjacentAllocationCreateUpdateView,
)

urlpatterns = [
    path('', ComplianceCalculationListCreate.as_view(), name='compliance-list-create'),
    path('<int:pk>/', ComplianceCalculationDetail.as_view(), name='compliance-detail'),
    path('recalculate/', ManualComplianceRecalculation.as_view(), name='compliance-recalculate'),
    path('adjacent-allocations/', AdjacentAllocationListView.as_view(), name='adjacent-allocation-list'),
    path('adjacent-allocations/<uuid:pk>/', AdjacentAllocationDetailView.as_view(), name='adjacent-allocation-detail'),
    path('adjacent-allocations/allocate/', AdjacentAllocationCreateUpdateView.as_view(), name='adjacent-allocation-create-update'),
]

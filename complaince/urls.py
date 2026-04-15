from django.urls import path
from .views import ComplianceCalculationListCreate, ComplianceCalculationDetail, ManualComplianceRecalculation

urlpatterns = [
    path('', ComplianceCalculationListCreate.as_view(), name='compliance-list-create'),
    path('<int:pk>/', ComplianceCalculationDetail.as_view(), name='compliance-detail'),
    path('recalculate/', ManualComplianceRecalculation.as_view(), name='compliance-recalculate'),
]

from django.urls import path
from .views import ComplianceCalculationListCreate, ComplianceCalculationDetail

urlpatterns = [
    path('', ComplianceCalculationListCreate.as_view(), name='compliance-list-create'),
    path('<int:pk>/', ComplianceCalculationDetail.as_view(), name='compliance-detail'),
]

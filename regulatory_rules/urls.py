from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import views

@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        "rules": "/rules/",
    })

urlpatterns = [
    path('', api_root),
    path('rules/', views.RegulatoryRuleListCreate.as_view(), name='rule-list'),
    path('rules/<int:pk>/', views.RegulatoryRuleDetail.as_view(), name='rule-detail'),
]
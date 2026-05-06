from django.urls import path
from .views import (
    SiteListCreate, SiteDetail, SiteApproveEvents, EventListing,
    SiteCensusDataImportExport, SiteCensusDataImportTemplate,
    ReallocateSiteAPIView, UndoReallocationAPIView, ReallocationHistoryAPIView,
    AdjacentCommunityAllocationView, AdjacentCommunityListCreate,
    ExcessReallocationOverviewView,
    MapAdjacentReallocationOverviewView,
    ToolCAdjacentReallocationListView,
    SiteBulkDelete,
)

urlpatterns = [
    # Site Census Data (Flat Format) CRUD
    path('', SiteListCreate.as_view(), name='site-list-create'),
    path('<int:pk>/', SiteDetail.as_view(), name='site-detail'),
    # Event Sites Approval
    path('approve-events/', SiteApproveEvents.as_view(), name='site-approve-events'),
    # Event Listing
    path('event-listing/', EventListing.as_view(), name='event-listing'),
    path('event-listing/<uuid:pk>/', EventListing.as_view(), name='event-listing-detail'),
    # Bulk delete SiteCensusData
    path('bulk-delete/', SiteBulkDelete.as_view(), name='site-bulk-delete'),
    # CSV Import/Export
    path('census-data/import-export/', SiteCensusDataImportExport.as_view(), name='site-census-data-import-export'),
    path('census-data/template/', SiteCensusDataImportTemplate.as_view(), name='site-census-data-template'),
    # Site Reallocation
    path('reallocate/', ReallocateSiteAPIView.as_view(), name='site-reallocate'),
    path('reallocation/<uuid:reallocation_id>/undo/', UndoReallocationAPIView.as_view(), name='reallocation-undo'),
    path('reallocation/history/<int:site_census_id>/', ReallocationHistoryAPIView.as_view(), name='reallocation-history'),
    # Adjacent Community Allocation View
    path('adjacent-allocation/', AdjacentCommunityAllocationView.as_view(), name='adjacent-allocation'),
    # Adjacent Community Management
    path('adjacency/', AdjacentCommunityListCreate.as_view(), name='adjacent-community'),
    # Excess reallocation overview
    path('excess-overview/', ExcessReallocationOverviewView.as_view(), name='excess-reallocation-overview'),
    # Tool C: map + legacy adjacency, regulatory % cap (default 35% of target required)
    path(
        'map-adjacent-reallocation/',
        MapAdjacentReallocationOverviewView.as_view(),
        name='map-adjacent-reallocation-overview',
    ),
    path(
        'tool-c-adjacent-reallocations/',
        ToolCAdjacentReallocationListView.as_view(),
        name='tool-c-adjacent-reallocations',
    ),
]
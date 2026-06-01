from django.urls import path

from .views import (
    SavedTourRouteStopDeleteView,
    SavedTourRouteStopStateView,
    TourRoutePoiDetailView,
    TourRouteView,
)

urlpatterns = [
    path("", TourRouteView.as_view(), name="tour-route"),
    path("pois/<str:stop_id>/", TourRoutePoiDetailView.as_view(), name="tour-route-poi-detail"),
    path(
        "saved/<int:route_id>/stops/<str:stop_id>/",
        SavedTourRouteStopDeleteView.as_view(),
        name="saved-tour-route-stop-delete",
    ),
    path(
        "saved/<int:route_id>/stops/<str:stop_id>/state/",
        SavedTourRouteStopStateView.as_view(),
        name="saved-tour-route-stop-state",
    ),
]

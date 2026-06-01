from django.urls import path

from .views import SavedTourRouteStopDeleteView, TourRouteView

urlpatterns = [
    path("", TourRouteView.as_view(), name="tour-route"),
    path(
        "saved/<int:route_id>/stops/<str:stop_id>/",
        SavedTourRouteStopDeleteView.as_view(),
        name="saved-tour-route-stop-delete",
    ),
]

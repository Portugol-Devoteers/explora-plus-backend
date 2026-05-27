from django.urls import path

from .views import TourRouteView

urlpatterns = [
    path("", TourRouteView.as_view(), name="tour-route"),
]

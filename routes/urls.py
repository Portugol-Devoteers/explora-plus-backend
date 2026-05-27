from django.urls import path

from .views import RouteListCreateView

urlpatterns = [
    path("routes/", RouteListCreateView.as_view(), name="route-list-create"),
]

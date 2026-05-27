from django.urls import include, path

urlpatterns = [
    path("api/tour-routes/", include("tour_routes.urls")),
]

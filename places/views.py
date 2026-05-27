from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Place
from .serializers import PlaceSerializer


class PlaceListView(APIView):
    """GET /api/places/?category=monumento"""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = (
            Place.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("images")
        )
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        serializer = PlaceSerializer(qs, many=True)
        return Response(serializer.data)


class PlaceDetailView(APIView):
    """GET /api/places/<slug>/"""

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug: str):
        place = get_object_or_404(
            Place.objects.select_related("category").prefetch_related("images"),
            slug=slug,
            is_active=True,
        )
        return Response(PlaceSerializer(place).data)

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class RouteListCreateView(APIView):
    """GET histórico do usuário; POST gera uma rota nova."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response([])

    def post(self, request):
        return Response({}, status=status.HTTP_201_CREATED)

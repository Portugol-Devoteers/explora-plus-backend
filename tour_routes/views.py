from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TourRouteRequestSerializer, serialize_result
from .services.exceptions import TourRouteError
from .services.planner import build_default_planner


class TourRouteView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TourRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        planner = build_default_planner()
        try:
            result, map_payload = planner.plan(
                origin_input=serializer.validated_data["origin"],
                destination_input=serializer.validated_data["destination"],
            )
        except TourRouteError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)

        return Response(serialize_result(result, map_payload))

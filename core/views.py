from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version();")
            postgis_version = cursor.fetchone()[0]
        db_status = "ok"
    except Exception as e:
        db_status = "error"
        postgis_version = str(e)

    return Response({
        "status": "ok",
        "db": db_status,
        "postgis": postgis_version,
    })

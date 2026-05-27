from __future__ import annotations

from urllib.error import HTTPError, URLError

from tour_routes.types import ResolvedPoint, RoutePath, GeoPoint

from .exceptions import RouteProviderError
from .http import JsonHttpClient


class OsrmWalkingRouter:
    endpoint = "https://router.project-osrm.org/route/v1/foot"

    def __init__(self, client: JsonHttpClient | None = None):
        self.client = client or JsonHttpClient()

    def route(self, origin: ResolvedPoint, destination: ResolvedPoint) -> RoutePath:
        coordinates = (
            f"{origin.location.lng},{origin.location.lat};"
            f"{destination.location.lng},{destination.location.lat}"
        )

        try:
            payload = self.client.get_json(
                f"{self.endpoint}/{coordinates}",
                params={
                    "overview": "full",
                    "geometries": "geojson",
                },
            )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise RouteProviderError("Nao foi possivel calcular a rota principal.") from exc

        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RouteProviderError("Nao foi possivel calcular a rota principal.")

        route = payload["routes"][0]
        geometry = route.get("geometry", {})
        raw_coordinates = geometry.get("coordinates") or []
        if not raw_coordinates:
            raise RouteProviderError("O provedor nao retornou geometria de rota.")

        return RoutePath(
            distance_m=int(round(route.get("distance", 0))),
            duration_s=int(round(route.get("duration", 0))),
            coordinates=[
                GeoPoint(lat=float(lat), lng=float(lng))
                for lng, lat in raw_coordinates
            ],
        )

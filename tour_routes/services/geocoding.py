from __future__ import annotations

from urllib.error import HTTPError, URLError

from tour_routes.types import GeoPoint, ResolvedPoint

from .exceptions import AddressResolutionError
from .http import JsonHttpClient


class NominatimGeocoder:
    endpoint = "https://nominatim.openstreetmap.org/search"

    def __init__(self, client: JsonHttpClient | None = None):
        self.client = client or JsonHttpClient()

    def resolve(self, address: str) -> ResolvedPoint:
        try:
            payload = self.client.get_json(
                self.endpoint,
                params={
                    "q": address,
                    "format": "jsonv2",
                    "limit": "1",
                },
            )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AddressResolutionError(
                f"Nao foi possivel localizar o endereco '{address}'."
            ) from exc

        if not payload:
            raise AddressResolutionError(
                f"Nao foi possivel localizar o endereco '{address}'."
            )

        match = payload[0]
        return ResolvedPoint(
            label=match.get("display_name") or address,
            location=GeoPoint(
                lat=float(match["lat"]),
                lng=float(match["lon"]),
            ),
        )

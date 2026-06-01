from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import quote

from django.utils import timezone

from tour_routes.constants import (
    TOUR_ROUTE_DETAIL_STATUS_COMPLETE,
    TOUR_ROUTE_DETAIL_STATUS_ERROR,
    TOUR_ROUTE_DETAIL_STATUS_UNAVAILABLE,
)
from tour_routes.models import TourRoutePoiDetail

from .http import JsonHttpClient


class TourRoutePoiDetailFetcher:
    nominatim_lookup_url = "https://nominatim.openstreetmap.org/lookup"
    wikidata_entities_url = "https://www.wikidata.org/w/api.php"
    wikipedia_summary_url = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

    def __init__(self, client: JsonHttpClient | None = None):
        self.client = client or JsonHttpClient()

    def hydrate(self, poi_detail: TourRoutePoiDetail) -> TourRoutePoiDetail:
        raw_payload = dict(poi_detail.raw_payload or {})
        address = poi_detail.address
        summary = poi_detail.summary
        image_url = poi_detail.image_url
        source_url = poi_detail.source_url or poi_detail.website
        website = poi_detail.website
        opening_hours = poi_detail.opening_hours
        wikipedia_title = poi_detail.wikipedia_title
        wikidata_id = poi_detail.wikidata_id

        try:
            lookup_payload = self._fetch_lookup_payload(poi_detail)
            if lookup_payload:
                raw_payload["nominatim"] = lookup_payload
                address = address or lookup_payload.get("display_name") or ""
                source_url = source_url or self._build_osm_url(
                    poi_detail.osm_type,
                    poi_detail.osm_id,
                )
                extratags = lookup_payload.get("extratags") or {}
                website = website or extratags.get("website") or extratags.get(
                    "contact:website"
                )
                opening_hours = opening_hours or extratags.get("opening_hours")
                wikipedia_title = wikipedia_title or self._normalize_wikipedia_title(
                    extratags.get("wikipedia")
                )
                wikidata_id = wikidata_id or extratags.get("wikidata")

            wikidata_payload = self._fetch_wikidata_payload(wikidata_id)
            if wikidata_payload:
                raw_payload["wikidata"] = wikidata_payload
                wikipedia_title = wikipedia_title or self._pick_wikipedia_title(
                    wikidata_payload
                )
                image_url = image_url or self._build_wikidata_image_url(wikidata_payload)

            summary_payload = self._fetch_wikipedia_summary(wikipedia_title)
            if summary_payload:
                raw_payload["wikipedia_summary"] = summary_payload
                summary = summary or summary_payload.get("extract") or ""
                image_url = image_url or self._extract_summary_image(summary_payload)
                source_url = source_url or self._extract_summary_source_url(
                    summary_payload
                )

            poi_detail.address = address or ""
            poi_detail.summary = summary or ""
            poi_detail.image_url = image_url or ""
            poi_detail.source_url = source_url or ""
            poi_detail.website = website or ""
            poi_detail.opening_hours = opening_hours or ""
            poi_detail.wikipedia_title = wikipedia_title or ""
            poi_detail.wikidata_id = wikidata_id or ""
            poi_detail.raw_payload = raw_payload
            poi_detail.detail_status = (
                TOUR_ROUTE_DETAIL_STATUS_COMPLETE
                if any(
                    [
                        poi_detail.address,
                        poi_detail.summary,
                        poi_detail.image_url,
                        poi_detail.source_url,
                        poi_detail.website,
                        poi_detail.opening_hours,
                    ]
                )
                else TOUR_ROUTE_DETAIL_STATUS_UNAVAILABLE
            )
        except (HTTPError, URLError, TimeoutError, ValueError):
            poi_detail.detail_status = TOUR_ROUTE_DETAIL_STATUS_ERROR
        finally:
            poi_detail.details_fetched_at = timezone.now()
            poi_detail.save(
                update_fields=[
                    "address",
                    "summary",
                    "image_url",
                    "source_url",
                    "website",
                    "opening_hours",
                    "wikipedia_title",
                    "wikidata_id",
                    "detail_status",
                    "raw_payload",
                    "details_fetched_at",
                    "updated_at",
                ]
            )

        return poi_detail

    def _fetch_lookup_payload(self, poi_detail: TourRoutePoiDetail) -> dict | None:
        if not poi_detail.osm_type or poi_detail.osm_id is None:
            return None

        osm_prefix = self._osm_lookup_prefix(poi_detail.osm_type)
        if osm_prefix is None:
            return None

        payload = self.client.get_json(
            self.nominatim_lookup_url,
            params={
                "format": "jsonv2",
                "addressdetails": "1",
                "extratags": "1",
                "namedetails": "1",
                "osm_ids": f"{osm_prefix}{poi_detail.osm_id}",
            },
            timeout=12.0,
        )
        if isinstance(payload, list) and payload:
            return payload[0]
        return None

    def _fetch_wikidata_payload(self, wikidata_id: str | None) -> dict | None:
        if not wikidata_id:
            return None

        payload = self.client.get_json(
            self.wikidata_entities_url,
            params={
                "action": "wbgetentities",
                "ids": wikidata_id,
                "format": "json",
                "props": "sitelinks|claims",
                "origin": "*",
            },
            timeout=12.0,
        )
        entity = (payload.get("entities") or {}).get(wikidata_id)
        if isinstance(entity, dict):
            return entity
        return None

    def _fetch_wikipedia_summary(self, wikipedia_title: str | None) -> dict | None:
        if not wikipedia_title:
            return None

        lang, title = self._split_wikipedia_title(wikipedia_title)
        if not title:
            return None

        return self.client.get_json(
            self.wikipedia_summary_url.format(lang=lang, title=quote(title)),
            timeout=12.0,
        )

    def _pick_wikipedia_title(self, wikidata_payload: dict) -> str | None:
        sitelinks = wikidata_payload.get("sitelinks") or {}
        for key in ("ptwiki", "enwiki"):
            entry = sitelinks.get(key)
            if entry and entry.get("title"):
                lang = key.removesuffix("wiki")
                return f"{lang}:{entry['title']}"
        return None

    def _build_wikidata_image_url(self, wikidata_payload: dict) -> str | None:
        claims = wikidata_payload.get("claims") or {}
        image_claims = claims.get("P18") or []
        if not image_claims:
            return None
        filename = (
            image_claims[0]
            .get("mainsnak", {})
            .get("datavalue", {})
            .get("value")
        )
        if not filename:
            return None
        return (
            "https://commons.wikimedia.org/wiki/Special:FilePath/"
            f"{quote(str(filename))}?width=1200"
        )

    def _extract_summary_image(self, summary_payload: dict) -> str | None:
        thumbnail = summary_payload.get("thumbnail") or {}
        original = summary_payload.get("originalimage") or {}
        return original.get("source") or thumbnail.get("source")

    def _extract_summary_source_url(self, summary_payload: dict) -> str | None:
        content_urls = summary_payload.get("content_urls") or {}
        desktop = content_urls.get("desktop") or {}
        mobile = content_urls.get("mobile") or {}
        return desktop.get("page") or mobile.get("page")

    def _build_osm_url(self, osm_type: str | None, osm_id: int | None) -> str | None:
        if not osm_type or osm_id is None:
            return None
        return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

    def _normalize_wikipedia_title(self, wikipedia_title: str | None) -> str | None:
        if not wikipedia_title:
            return None
        normalized = wikipedia_title.strip()
        return normalized or None

    def _split_wikipedia_title(self, wikipedia_title: str) -> tuple[str, str]:
        if ":" not in wikipedia_title:
            return "pt", wikipedia_title.strip().replace(" ", "_")
        lang, title = wikipedia_title.split(":", 1)
        return lang.strip() or "pt", title.strip().replace(" ", "_")

    def _osm_lookup_prefix(self, osm_type: str) -> str | None:
        normalized = osm_type.casefold()
        if normalized == "node":
            return "N"
        if normalized == "way":
            return "W"
        if normalized == "relation":
            return "R"
        return None


def build_poi_detail_fetcher() -> TourRoutePoiDetailFetcher:
    return TourRoutePoiDetailFetcher()

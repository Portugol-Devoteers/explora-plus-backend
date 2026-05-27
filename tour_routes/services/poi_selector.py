from __future__ import annotations

from tour_routes.types import PoiCandidate

from .geometry import haversine_distance_m, sample_route_positions

SEGMENT_TARGET_M = 100.0
SEGMENT_WINDOW_M = 50.0
DEDUP_DISTANCE_M = 40.0


class PoiSelector:
    def select(
        self, candidates: list[PoiCandidate], route_distance_m: int
    ) -> list[PoiCandidate]:
        if not candidates:
            return []

        deduplicated = self._deduplicate(candidates)
        sample_positions = sample_route_positions(route_distance_m, interval_m=SEGMENT_TARGET_M)

        chosen: list[PoiCandidate] = []
        chosen_ids: set[int] = set()

        for target in sample_positions:
            eligible = [
                candidate
                for candidate in deduplicated
                if id(candidate) not in chosen_ids
                and abs(candidate.progress_m - target) <= SEGMENT_WINDOW_M
            ]
            if not eligible:
                continue

            best = min(
                eligible,
                key=lambda candidate: (
                    candidate.priority,
                    candidate.distance_from_route_m,
                    abs(candidate.progress_m - target),
                    candidate.name.casefold(),
                ),
            )
            chosen.append(best)
            chosen_ids.add(id(best))

        return sorted(chosen, key=lambda candidate: candidate.progress_m)

    def _deduplicate(self, candidates: list[PoiCandidate]) -> list[PoiCandidate]:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                candidate.priority,
                candidate.distance_from_route_m,
                candidate.progress_m,
                candidate.name.casefold(),
            ),
        )

        deduplicated: list[PoiCandidate] = []
        for candidate in ordered:
            normalized_name = self._normalize_name(candidate.name)
            already_exists = False
            for existing in deduplicated:
                if self._normalize_name(existing.name) != normalized_name:
                    continue
                if (
                    haversine_distance_m(existing.location, candidate.location)
                    <= DEDUP_DISTANCE_M
                ):
                    already_exists = True
                    break
            if not already_exists:
                deduplicated.append(candidate)

        return deduplicated

    def _normalize_name(self, value: str) -> str:
        return " ".join(value.casefold().split())

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    TOUR_ROUTE_CATEGORY_CULTURE,
    TOUR_ROUTE_CATEGORY_FOOD,
    TOUR_ROUTE_CATEGORY_PARK,
    TOUR_ROUTE_DEFAULT_INCLUDE_CULTURE,
    TOUR_ROUTE_DEFAULT_INCLUDE_FOOD,
    TOUR_ROUTE_DEFAULT_INCLUDE_PARK,
    TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M,
    TOUR_ROUTE_DEFAULT_POI_SPACING_M,
)
from .models import UserRouteSearchPreference


@dataclass(frozen=True)
class TourRouteSearchPreferences:
    include_culture: bool = TOUR_ROUTE_DEFAULT_INCLUDE_CULTURE
    include_park: bool = TOUR_ROUTE_DEFAULT_INCLUDE_PARK
    include_food: bool = TOUR_ROUTE_DEFAULT_INCLUDE_FOOD
    poi_spacing_m: int = TOUR_ROUTE_DEFAULT_POI_SPACING_M
    max_search_radius_m: int = TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M

    @property
    def enabled_categories(self) -> tuple[str, ...]:
        categories: list[str] = []
        if self.include_culture:
            categories.append(TOUR_ROUTE_CATEGORY_CULTURE)
        if self.include_park:
            categories.append(TOUR_ROUTE_CATEGORY_PARK)
        if self.include_food:
            categories.append(TOUR_ROUTE_CATEGORY_FOOD)
        return tuple(categories)

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "include_culture": self.include_culture,
            "include_park": self.include_park,
            "include_food": self.include_food,
            "poi_spacing_m": self.poi_spacing_m,
            "max_search_radius_m": self.max_search_radius_m,
        }


def get_default_search_preferences() -> TourRouteSearchPreferences:
    return TourRouteSearchPreferences()


def get_search_preferences_for_user(user) -> TourRouteSearchPreferences:
    if not getattr(user, "is_authenticated", False):
        return get_default_search_preferences()

    model = (
        UserRouteSearchPreference.objects.filter(user=user)
        .only(
            "include_culture",
            "include_park",
            "include_food",
            "poi_spacing_m",
            "max_search_radius_m",
        )
        .first()
    )
    if model is None:
        return get_default_search_preferences()
    return search_preferences_from_model(model)


def save_search_preferences_for_user(
    user,
    *,
    include_culture: bool,
    include_park: bool,
    include_food: bool,
    poi_spacing_m: int,
    max_search_radius_m: int,
) -> TourRouteSearchPreferences:
    model, _ = UserRouteSearchPreference.objects.update_or_create(
        user=user,
        defaults={
            "include_culture": include_culture,
            "include_park": include_park,
            "include_food": include_food,
            "poi_spacing_m": poi_spacing_m,
            "max_search_radius_m": max_search_radius_m,
        },
    )
    return search_preferences_from_model(model)


def search_preferences_from_model(
    model: UserRouteSearchPreference,
) -> TourRouteSearchPreferences:
    return TourRouteSearchPreferences(
        include_culture=bool(model.include_culture),
        include_park=bool(model.include_park),
        include_food=bool(model.include_food),
        poi_spacing_m=int(model.poi_spacing_m),
        max_search_radius_m=int(model.max_search_radius_m),
    )

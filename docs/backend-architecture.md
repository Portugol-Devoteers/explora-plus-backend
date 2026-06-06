# Backend Architecture

## Active domains

- `places` is the canonical domain for every place/POI in the system.
- `tour_routes` is the route-planning feature layer.
- `accounts` owns auth and the current user contract.
- `tickets` remains isolated and is not part of the active route/place refactor.

## Canonical place model

Every POI discovered during route planning is materialized into `places.Place`.

Current canonical entities:

- `PlaceCategory`
- `Place`
- `PlaceImage`
- `UserPlaceState`

`Place` now holds both curated content and externally discovered POI metadata:

- editorial fields like `description`
- operational fields like `source_ref`, `osm_id`, `wikidata_id`, `summary`
- detail enrichment fields like `source_url`, `website`, `opening_hours`

## Tour route persistence

`tour_routes` no longer treats JSON snapshots as the primary source of truth for user routes.

Current entities:

- `UserRouteSearchPreference`: persisted planner settings for an authenticated user
- `RouteSearchCache`: base planner/cache payload
- `TourRoute`: persisted current/historic route for a user
- `TourRouteStop`: relational stop list for the route

Route personalization rules:

- planner search settings live in `tour_routes.UserRouteSearchPreference`
- saved preferences apply only to the next `POST /api/tour-routes/`
- global visited state lives in `places.UserPlaceState`
- route-only exclusion lives in `tour_routes.TourRouteStop.state`
- active API responses are rebuilt from relational route data
- cache JSON remains only as technical input for recalculating a personalized route
- cache keys include effective search preferences as well as origin/destination

## Compatibility boundary

The frontend MVP contract remains stable:

- `POST /api/tour-routes/`
- `GET /api/tour-routes/preferences/`
- `PATCH /api/tour-routes/preferences/`
- `GET /api/tour-routes/current/`
- `GET /api/tour-routes/places/`
- `PATCH /api/tour-routes/places/<stop_id>/visited/`
- `GET /api/tour-routes/pois/<stop_id>/`

Legacy `/api/places/` endpoints still exist, but they now read from the same canonical `Place` table used by route planning.

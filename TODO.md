# Backend - TODO Atual

## Estado real do projeto

- O backend ativo agora gira em torno de `accounts + places + tour_routes + tickets`.
- `places` e o dominio canonico de lugares/POIs.
- `tour_routes` e a feature principal de planejamento, rota atual, historico e biblioteca pessoal.
- `routes` saiu do caminho ativo e nao deve receber novas features.
- O ambiente principal de desenvolvimento do backend e Docker + PostGIS.

## Arquitetura consolidada

### Places
- `PlaceCategory`: taxonomia canonica (`culture`, `park`, `food`)
- `Place`: lugar unificado, tanto curado quanto descoberto via APIs externas
- `PlaceImage`: imagens do lugar
- `UserPlaceState`: estado global do usuario sobre um lugar (`visited`, aparicoes, ultima rota)

### Tour Routes
- `RouteSearchCache`: cache tecnico da busca e do payload-base do planner
- `TourRoute`: snapshot relacional da rota atual/historica do usuario
- `TourRouteStop`: stops relacionais da rota com estado `active|visited|excluded`

## O que ja esta pronto

- Auth JWT com `register`, `login`, `refresh` e `/api/me/`
- `/api/places/` e `/api/places/<slug>/`
- `/api/tour-routes/`
- `/api/tour-routes/current/`
- `/api/tour-routes/places/`
- `/api/tour-routes/places/<stop_id>/visited/`
- `/api/tour-routes/pois/<stop_id>/`
- exclusao e marcacao de stop na rota atual

## Proximos passos recomendados

1. Revisar o frontend legado que ainda consome `places.ts` e alinhar a taxonomia antiga com a nova.
2. Decidir se `tickets` vai continuar no MVP ou se deve ser ocultado/isolado de vez.
3. Atualizar seeds e catalogo curado para a taxonomia `culture|park|food`.
4. Refinar admin e curadoria para reconciliar POIs externos com lugares curados.
5. Se fizer sentido, criar uma 2a fase para padronizar tambem o contrato HTTP antigo de `/api/places/`.

## Fora de escopo desta fase

- Pagamento real de ingressos
- Reintroduzir o app `routes`
- Rodar GIS completo fora do Docker
- Internacionalizacao

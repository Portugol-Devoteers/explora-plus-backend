# Tour Routes API

## Objetivo

O endpoint `POST /api/tour-routes/` calcula primeiro uma rota direta a pe entre origem e destino, usa esse trajeto para descobrir pontos de interesse e, quando possivel, monta uma rota turistica hibrida passando por todos os pontos selecionados.

A resposta devolve:

- `route`: dados da rota ativa para o app desenhar
- `route.direct_route`: a linha direta do OSRM a pe guardada para comparacao e fallback
- `route.places_to_pass`: a lista completa de sugestoes, indicando quais viraram paradas reais
- `map`: um GeoJSON pronto para o app renderizar rota turistica, rota direta e marcadores

Este servico nao usa autenticacao nem banco de dados.

## Endpoint

`POST /api/tour-routes/`

## Request

Cada ponta da rota aceita **exatamente um** destes formatos:

- `address`: texto livre do endereco
- `location`: coordenadas `lat` e `lng`

### Exemplo com enderecos

```json
{
  "origin": { "address": "Av. Paulista, 1578, Sao Paulo" },
  "destination": { "address": "Av. Paulista, 2300, Sao Paulo" }
}
```

### Exemplo com coordenadas

```json
{
  "origin": { "location": { "lat": -23.561399, "lng": -46.655881 } },
  "destination": { "location": { "lat": -23.555070, "lng": -46.639550 } }
}
```

## Response

```json
{
  "route": {
    "mode": "tour",
    "origin": {
      "label": "Av. Paulista, 1578 - Bela Vista, Sao Paulo",
      "location": { "lat": -23.561399, "lng": -46.655881 }
    },
    "destination": {
      "label": "Av. Paulista, 2300 - Cerqueira Cesar, Sao Paulo",
      "location": { "lat": -23.555070, "lng": -46.639550 }
    },
    "distance_m": 540,
    "duration_s": 510,
    "polyline_points": [
      { "lat": -23.561399, "lng": -46.655881 },
      { "lat": -23.561414, "lng": -46.655881 },
      { "lat": -23.561100, "lng": -46.653000 },
      { "lat": -23.568000, "lng": -46.640800 },
      { "lat": -23.555070, "lng": -46.639550 }
    ],
    "direct_route": {
      "distance_m": 360,
      "duration_s": 280,
      "polyline_points": [
        { "lat": -23.561399, "lng": -46.655881 },
        { "lat": -23.559100, "lng": -46.650100 },
        { "lat": -23.557200, "lng": -46.644800 },
        { "lat": -23.555070, "lng": -46.639550 }
      ]
    },
    "places_to_pass": [
      {
        "order": 1,
        "name": "MASP",
        "category": "culture",
        "location": { "lat": -23.561414, "lng": -46.655881 },
        "distance_from_route_m": 12,
        "source": "overpass",
        "included_in_route": true,
        "waypoint_order": 1
      }
    ]
  },
  "map": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": { "type": "LineString", "coordinates": [] },
        "properties": { "kind": "route_tour", "active": true }
      },
      {
        "type": "Feature",
        "geometry": { "type": "LineString", "coordinates": [] },
        "properties": { "kind": "route_direct", "active": false }
      },
      {
        "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [] },
        "properties": { "kind": "stop", "waypoint_order": 1 }
      }
    ]
  }
}
```

## Campos principais

### `route`

- `mode`: `tour` quando a rota multi-parada ficou pronta, `direct_fallback` quando o app deve usar a rota direta
- `origin` e `destination`: pontos resolvidos pelo backend
- `distance_m`, `duration_s` e `polyline_points`: sempre descrevem a rota ativa
- `direct_route`: copia da rota direta original para comparacao e fallback
- `places_to_pass`: lista ordenada completa de pontos de interesse
- `included_in_route`: informa se o ponto entrou como parada real
- `waypoint_order`: ordem real da visita quando o ponto entrou na rota turistica

### `map`

- sempre retorna um GeoJSON `FeatureCollection`
- contem um `LineString` `route_tour` quando a rota turistica foi calculada
- contem um `LineString` `route_direct` com a linha original
- contem `Point`s para origem, destino, paradas reais (`stop`) e sugestoes extras (`poi`)
- o app pode renderizar esse GeoJSON do jeito que preferir

## Exemplo com curl

```bash
curl -X POST http://localhost:8080/api/tour-routes/ \
  -H "Content-Type: application/json" \
  -d '{
    "origin": { "address": "Av. Paulista, 1578, Sao Paulo" },
    "destination": { "address": "Av. Paulista, 2300, Sao Paulo" }
  }'
```

## Modos de operacao

- `tour`: a rota ativa passa por todos os POIs selecionados usando trechos detalhados a pe entre as paradas, mas pode cortar diretamente pequenos saltos quando o mapa de ruas faz um contorno exagerado
- `direct_fallback`: a rota ativa fica direta porque nao havia POIs suficientes ou porque a rota turistica nao ficou disponivel

## Erros esperados

- `400`: request invalido ou endereco nao encontrado
- `502`: falha ao calcular a rota principal

Se a busca de pontos de interesse falhar, a API ainda devolve `200` com a rota ativa disponivel e `places_to_pass` vazio.

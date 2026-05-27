# Tour Routes API

## Objetivo

O endpoint `POST /api/tour-routes/` calcula uma rota principal a pe entre origem e destino e sugere lugares interessantes proximos desse trajeto. A resposta devolve:

- `route`: dados da rota e a lista ordenada de lugares pelos quais vale passar
- `map`: um GeoJSON pronto para o app renderizar a linha da rota e os marcadores

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
    "origin": {
      "label": "Av. Paulista, 1578 - Bela Vista, Sao Paulo",
      "location": { "lat": -23.561399, "lng": -46.655881 }
    },
    "destination": {
      "label": "Av. Paulista, 2300 - Cerqueira Cesar, Sao Paulo",
      "location": { "lat": -23.555070, "lng": -46.639550 }
    },
    "distance_m": 360,
    "duration_s": 280,
    "polyline_points": [
      { "lat": -23.561399, "lng": -46.655881 },
      { "lat": -23.559100, "lng": -46.650100 },
      { "lat": -23.557200, "lng": -46.644800 },
      { "lat": -23.555070, "lng": -46.639550 }
    ],
    "places_to_pass": [
      {
        "order": 1,
        "name": "MASP",
        "category": "culture",
        "location": { "lat": -23.561414, "lng": -46.655881 },
        "distance_from_route_m": 12,
        "source": "overpass"
      }
    ]
  },
  "map": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

## Campos principais

### `route`

- `origin` e `destination`: pontos resolvidos pelo backend
- `distance_m`: distancia total estimada da rota principal
- `duration_s`: duracao estimada a pe
- `polyline_points`: lista de coordenadas da rota principal
- `places_to_pass`: lista ordenada de pontos de interesse proximos da rota

### `map`

- sempre retorna um GeoJSON `FeatureCollection`
- contem um `LineString` para a rota
- contem `Point`s para origem, destino e pontos de interesse
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

## Erros esperados

- `400`: request invalido ou endereco nao encontrado
- `502`: falha ao calcular a rota principal

Se a busca de pontos de interesse falhar, a API ainda devolve `200` com a rota principal e `places_to_pass` vazio.

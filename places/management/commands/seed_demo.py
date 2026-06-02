from datetime import datetime, timedelta, timezone

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from places.models import Place, PlaceCategory, PlaceImage

CATEGORIES = [
    {"slug": "culture", "name": "Cultura", "icon_name": "camera"},
    {"slug": "park", "name": "Parques", "icon_name": "leaf"},
    {"slug": "food", "name": "Comida", "icon_name": "restaurant"},
]


def now_plus(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=days)


PLACES = [
    {
        "slug": "aquario-municipal-santos",
        "category": "culture",
        "name": "Aquário Municipal de Santos",
        "description": (
            "Inaugurado em 1945 na Ponta da Praia, é um dos aquários mais antigos do Brasil. "
            "Reúne tubarões, peixes-boi-marinhos, pinguins, leões-marinhos e dezenas de espécies "
            "do litoral paulista. Visita rápida (cerca de 1h) e ótima pra quem viaja com criança."
        ),
        "lat": -23.9851,
        "lng": -46.3061,
        "address": "Pç. Luiz La Scala, s/n – Ponta da Praia",
        "hours_open": "09:00 - 17:30",
        "price_cents": 1200,
        "images": [
            "https://images.unsplash.com/photo-1571167530149-c1105da4c2c7?w=1200&q=80",
            "https://images.unsplash.com/photo-1583212292454-1fe6229603b7?w=1200&q=80",
            "https://images.unsplash.com/photo-1602407294553-6ac9170b3ed0?w=1200&q=80",
        ],
    },
    {
        "slug": "monte-serrat",
        "category": "culture",
        "name": "Santuário do Monte Serrat",
        "description": (
            "Padroeira da cidade, fica no topo do morro mais alto da região central. "
            "O acesso é por funicular (bondinho inclinado) ou trilha. Lá em cima você tem "
            "a melhor vista panorâmica de Santos, do porto e da orla — vai no fim de tarde "
            "que o pôr-do-sol é cinema."
        ),
        "lat": -23.9388,
        "lng": -46.3247,
        "address": "Pç. Correia de Mello, s/n – Centro",
        "hours_open": "08:00 - 18:00",
        "price_cents": 800,
        "images": [
            "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=1200&q=80",
            "https://images.unsplash.com/photo-1499678329028-101435549a4e?w=1200&q=80",
        ],
    },
    {
        "slug": "pinacoteca-benedicto-calixto",
        "category": "culture",
        "name": "Pinacoteca Benedicto Calixto",
        "description": (
            "Casarão histórico no centro com acervo permanente do pintor santista Benedicto "
            "Calixto, célebre por suas marinhas. Mantém também exposições temporárias de arte "
            "contemporânea. Entrada gratuita."
        ),
        "lat": -23.9647,
        "lng": -46.3300,
        "address": "Rua Pedro Lessa, 366 – Embaré",
        "hours_open": "10:00 - 18:00",
        "price_cents": 0,
        "images": [
            "https://images.unsplash.com/photo-1543349689-9a4d426bee8e?w=1200&q=80",
            "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=1200&q=80",
        ],
    },
    {
        "slug": "orquidario-municipal",
        "category": "park",
        "name": "Orquidário Municipal",
        "description": (
            "Parque urbano com mais de 3.500 orquídeas, mata atlântica preservada, lago com "
            "aves aquáticas e um pequeno zoológico de animais resgatados. Refúgio verde no "
            "meio da cidade — pega umas duas horas tranquilas."
        ),
        "lat": -23.9554,
        "lng": -46.3219,
        "address": "Pç. Washington, s/n – José Menino",
        "hours_open": "08:00 - 17:00",
        "price_cents": 500,
        "images": [
            "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=1200&q=80",
            "https://images.unsplash.com/photo-1466692476868-aef1dfb1e735?w=1200&q=80",
        ],
    },
    {
        "slug": "museu-pele",
        "category": "culture",
        "name": "Museu Pelé",
        "description": (
            "Casarão eclético tombado, restaurado pra abrigar a história do maior jogador "
            "de futebol de todos os tempos. Mistura arquivos pessoais, troféus, vídeos e "
            "instalações interativas. Parada obrigatória pra fã de futebol em Santos."
        ),
        "lat": -23.9333,
        "lng": -46.3328,
        "address": "Largo Marquês de Monte Alegre, s/n – Centro Histórico",
        "hours_open": "10:00 - 18:00",
        "price_cents": 1500,
        "images": [
            "https://images.unsplash.com/photo-1551918120-9739cb430c6d?w=1200&q=80",
            "https://images.unsplash.com/photo-1564604761-2c5dbf6f7da9?w=1200&q=80",
        ],
    },
    {
        "slug": "museu-do-cafe",
        "category": "food",
        "name": "Museu do Café",
        "description": (
            "Funciona no prédio da antiga Bolsa Oficial de Café, ícone do auge do ciclo "
            "cafeeiro brasileiro. O salão dos pregões é deslumbrante. Tem cafeteria nos "
            "fundos servindo cafés especiais de todo o país — vale só pela cafeteria."
        ),
        "lat": -23.9325,
        "lng": -46.3300,
        "address": "Rua XV de Novembro, 95 – Centro",
        "hours_open": "09:00 - 17:00",
        "price_cents": 1000,
        "images": [
            "https://images.unsplash.com/photo-1583779457094-ab6f9164a1c8?w=1200&q=80",
            "https://images.unsplash.com/photo-1558642084-fd07fae5282e?w=1200&q=80",
        ],
    },
    {
        "slug": "catedral-de-santos",
        "category": "culture",
        "name": "Catedral de Santos",
        "description": (
            "Igreja matriz de estilo neogótico, com vitrais coloridos e a maior nave da "
            "Baixada Santista. Construção iniciada em 1909 e concluída só em 1967. "
            "Entrada gratuita, vale dar uma volta tranquila pelo entorno do Centro Histórico."
        ),
        "lat": -23.9358,
        "lng": -46.3275,
        "address": "Pç. Patriarca José Bonifácio, s/n – Centro",
        "hours_open": "07:00 - 19:00",
        "price_cents": 0,
        "images": [
            "https://images.unsplash.com/photo-1543349689-9a4d426bee8e?w=1200&q=80",
            "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200&q=80",
        ],
    },
    {
        "slug": "bonde-turistico-santos",
        "category": "culture",
        "name": "Bonde Turístico de Santos",
        "description": (
            "Bondes antigos restaurados que fazem um circuito de cerca de 1,7 km pelo "
            "Centro Histórico, passando por casarões, igrejas e o prédio da Bolsa do Café. "
            "Saídas de hora em hora, do Largo Marquês de Monte Alegre."
        ),
        "lat": -23.9319,
        "lng": -46.3306,
        "address": "Estação Valongo – Pç. Mauá – Centro",
        "hours_open": "11:00 - 17:00",
        "price_cents": 700,
        "images": [
            "https://images.unsplash.com/photo-1488459716781-31db52582fe9?w=1200&q=80",
            "https://images.unsplash.com/photo-1533900298318-6b8da08a523e?w=1200&q=80",
        ],
    },
    {
        "slug": "festival-do-cafe",
        "category": "food",
        "name": "Festival do Café Santista",
        "description": (
            "Festival anual no Museu do Café reunindo torrefadores, baristas, produtores "
            "rurais e cafeterias artesanais. Tem degustação, workshops, latte art e palestras "
            "sobre cafés especiais."
        ),
        "lat": -23.9325,
        "lng": -46.3300,
        "address": "Museu do Café – Rua XV de Novembro, 95",
        "hours_open": "09:00 - 19:00",
        "price_cents": 2500,
        "event_start_at": now_plus(7),
        "event_end_at": now_plus(10),
        "images": [
            "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&q=80",
            "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=1200&q=80",
        ],
    },
    {
        "slug": "mostra-verao-pinacoteca",
        "category": "culture",
        "name": "Mostra de Verão da Pinacoteca",
        "description": (
            "Mostra coletiva anual da Pinacoteca Benedicto Calixto trazendo artistas "
            "contemporâneos do litoral paulista. Entrada gratuita, com mediação cultural "
            "nos fins de semana."
        ),
        "lat": -23.9647,
        "lng": -46.3300,
        "address": "Pinacoteca – Rua Pedro Lessa, 366",
        "hours_open": "10:00 - 18:00",
        "price_cents": 0,
        "event_start_at": now_plus(30),
        "event_end_at": now_plus(75),
        "images": [
            "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200&q=80",
            "https://images.unsplash.com/photo-1533900298318-6b8da08a523e?w=1200&q=80",
        ],
    },
]


class Command(BaseCommand):
    help = "Popula categorias e ~10 lugares de Santos para demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga todos os Places/PlaceImages antes de popular.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            self.stdout.write(self.style.WARNING("Apagando Places existentes…"))
            PlaceImage.objects.all().delete()
            Place.objects.all().delete()

        cats_by_slug: dict[str, PlaceCategory] = {}
        for c in CATEGORIES:
            obj, created = PlaceCategory.objects.update_or_create(
                slug=c["slug"], defaults={"name": c["name"], "icon_name": c["icon_name"]}
            )
            cats_by_slug[c["slug"]] = obj
            self.stdout.write(
                f"  {'+' if created else '·'} Categoria: {obj.name}"
            )

        for p in PLACES:
            place, created = Place.objects.update_or_create(
                slug=p["slug"],
                defaults={
                    "category": cats_by_slug[p["category"]],
                    "name": p["name"],
                    "description": p["description"],
                    "location": Point(p["lng"], p["lat"], srid=4326),
                    "address": p["address"],
                    "opening_hours": p["hours_open"],
                    "summary": p["description"],
                    "source": "curated",
                    "is_curated": True,
                    "price_cents": p["price_cents"],
                    "currency": "BRL",
                    "event_start_at": p.get("event_start_at"),
                    "event_end_at": p.get("event_end_at"),
                    "is_active": True,
                },
            )
            place.images.all().delete()
            for i, url in enumerate(p["images"]):
                PlaceImage.objects.create(place=place, url=url, order=i)
            self.stdout.write(
                f"  {'+' if created else '·'} {place.name} "
                f"({len(p['images'])} imagens)"
            )

        self.stdout.write(self.style.SUCCESS("\nSeed concluído ✓"))

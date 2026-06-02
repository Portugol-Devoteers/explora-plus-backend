from django.conf import settings
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("places", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RouteSearchCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cache_key", models.CharField(max_length=64, unique=True)),
                ("origin_query", models.CharField(blank=True, max_length=255)),
                ("destination_query", models.CharField(blank=True, max_length=255)),
                ("search_payload", models.JSONField(blank=True, default=dict)),
                ("route_payload", models.JSONField(blank=True, default=dict)),
                ("map_payload", models.JSONField(blank=True, default=dict)),
                ("hit_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Route search cache",
                "verbose_name_plural": "Route search caches",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="TourRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origin_query", models.CharField(blank=True, max_length=255)),
                ("destination_query", models.CharField(blank=True, max_length=255)),
                ("origin_label", models.CharField(blank=True, max_length=255)),
                ("destination_label", models.CharField(blank=True, max_length=255)),
                ("origin_location", django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ("destination_location", django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ("mode", models.CharField(default="tour", max_length=32)),
                ("distance_m", models.PositiveIntegerField(default=0)),
                ("duration_s", models.PositiveIntegerField(default=0)),
                ("direct_distance_m", models.PositiveIntegerField(default=0)),
                ("direct_duration_s", models.PositiveIntegerField(default=0)),
                ("route_geometry", django.contrib.gis.db.models.fields.LineStringField(blank=True, geography=True, null=True, srid=4326)),
                ("direct_route_geometry", django.contrib.gis.db.models.fields.LineStringField(blank=True, geography=True, null=True, srid=4326)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("search_cache", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routes", to="tour_routes.routesearchcache")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tour_routes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Tour route",
                "verbose_name_plural": "Tour routes",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="TourRouteStop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_order", models.PositiveIntegerField()),
                ("waypoint_order", models.PositiveIntegerField(blank=True, null=True)),
                ("state", models.CharField(choices=[("active", "Active"), ("visited", "Visited"), ("excluded", "Excluded")], default="active", max_length=16)),
                ("source", models.CharField(blank=True, max_length=32)),
                ("distance_from_route_m", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("place", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="route_stops", to="places.place")),
                ("route", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stops", to="tour_routes.tourroute")),
            ],
            options={
                "verbose_name": "Tour route stop",
                "verbose_name_plural": "Tour route stops",
                "ordering": ["display_order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="tourroute",
            index=models.Index(fields=["user", "-created_at"], name="tour_routes_user_id_6eeefe_idx"),
        ),
        migrations.AddConstraint(
            model_name="tourroutestop",
            constraint=models.UniqueConstraint(fields=("route", "place"), name="tour_routes_unique_route_place"),
        ),
        migrations.AddConstraint(
            model_name="tourroutestop",
            constraint=models.UniqueConstraint(fields=("route", "display_order"), name="tour_routes_unique_route_display_order"),
        ),
        migrations.AddIndex(
            model_name="tourroutestop",
            index=models.Index(fields=["route", "state"], name="tour_routes_route_i_7f59de_idx"),
        ),
        migrations.AddIndex(
            model_name="tourroutestop",
            index=models.Index(fields=["route", "waypoint_order"], name="tour_routes_route_i_b74478_idx"),
        ),
    ]

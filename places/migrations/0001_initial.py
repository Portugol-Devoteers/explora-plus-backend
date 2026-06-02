from django.conf import settings
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlaceCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("icon_name", models.CharField(blank=True, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Place category",
                "verbose_name_plural": "Place categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Place",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("source", models.CharField(choices=[("curated", "Curated"), ("overpass", "Overpass"), ("cache", "Cache")], default="curated", max_length=32)),
                ("source_ref", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("location", django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("opening_hours", models.CharField(blank=True, max_length=255)),
                ("price_cents", models.PositiveIntegerField(blank=True, null=True)),
                ("currency", models.CharField(default="BRL", max_length=3)),
                ("event_start_at", models.DateTimeField(blank=True, null=True)),
                ("event_end_at", models.DateTimeField(blank=True, null=True)),
                ("osm_type", models.CharField(blank=True, max_length=16)),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("wikidata_id", models.CharField(blank=True, max_length=64)),
                ("wikipedia_title", models.CharField(blank=True, max_length=255)),
                ("source_url", models.URLField(blank=True)),
                ("website", models.URLField(blank=True)),
                ("detail_status", models.CharField(default="pending", max_length=32)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("details_fetched_at", models.DateTimeField(blank=True, null=True)),
                ("is_curated", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="places", to="places.placecategory")),
            ],
            options={
                "verbose_name": "Place",
                "verbose_name_plural": "Places",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="PlaceImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(max_length=500)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("caption", models.CharField(blank=True, max_length=200)),
                ("place", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="places.place")),
            ],
            options={
                "verbose_name": "Place image",
                "verbose_name_plural": "Place images",
                "ordering": ["place", "order", "id"],
            },
        ),
        migrations.CreateModel(
            name="UserPlaceState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_visited", models.BooleanField(default=False)),
                ("visited_at", models.DateTimeField(blank=True, null=True)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("seen_count", models.PositiveIntegerField(default=1)),
                ("place", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_states", to="places.place")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="place_states", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "User place state",
                "verbose_name_plural": "User place states",
                "ordering": ["-last_seen_at"],
            },
        ),
        migrations.AddIndex(
            model_name="place",
            index=models.Index(fields=["category", "is_active"], name="places_plac_categor_e4ca4c_idx"),
        ),
        migrations.AddIndex(
            model_name="place",
            index=models.Index(fields=["source", "is_active"], name="places_plac_source__690193_idx"),
        ),
        migrations.AddConstraint(
            model_name="userplacestate",
            constraint=models.UniqueConstraint(fields=("user", "place"), name="places_unique_user_place_state"),
        ),
        migrations.AddIndex(
            model_name="userplacestate",
            index=models.Index(fields=["user", "-last_seen_at"], name="places_user_user_id_bae298_idx"),
        ),
        migrations.AddIndex(
            model_name="userplacestate",
            index=models.Index(fields=["user", "is_visited"], name="places_user_user_id_93f5d6_idx"),
        ),
    ]

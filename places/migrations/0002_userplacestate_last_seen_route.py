import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0001_initial"),
        ("tour_routes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userplacestate",
            name="last_seen_route",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="seen_place_states",
                to="tour_routes.tourroute",
            ),
        ),
    ]

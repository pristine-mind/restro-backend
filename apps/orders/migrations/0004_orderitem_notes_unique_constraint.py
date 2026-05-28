from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_orderitem_station_orderstationlog"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="orderitem",
            name="unique_order_item",
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(fields=("order", "menu_item", "notes"), name="unique_order_item"),
        ),
    ]
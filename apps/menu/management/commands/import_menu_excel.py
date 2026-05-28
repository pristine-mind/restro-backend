from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.menu.models import Category, MenuItem


class Command(BaseCommand):
    help = "Import menu categories and items from an Excel file."

    REQUIRED_COLUMNS = {"name", "price", "category"}
    STATION_ALIASES = {
        "kitchen": Category.Station.KITCHEN,
        "bar": Category.Station.BAR,
    }

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the Excel file to import.")
        parser.add_argument(
            "--default-station",
            choices=[Category.Station.KITCHEN, Category.Station.BAR],
            default=Category.Station.KITCHEN,
            help="Station to assign to newly created categories when the sheet does not specify one.",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default=0,
            help="Worksheet name or index to import. Defaults to the first sheet.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"]).expanduser()
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        dataframe = self.load_dataframe(file_path, options["sheet"])
        created_categories = 0
        updated_categories = 0
        created_items = 0
        updated_items = 0

        with transaction.atomic():
            for row_number, row in enumerate(dataframe.to_dict(orient="records"), start=2):
                normalized_row = self.normalize_row(row, row_number)
                category, category_created = Category.objects.get_or_create(
                    name=normalized_row["category"],
                    defaults={
                        "display_order": self.next_display_order(),
                        "station": normalized_row["station"] or options["default_station"],
                    },
                )
                if category_created:
                    created_categories += 1
                    self.stdout.write(f"Created category: {category.name}")
                elif normalized_row["station"] and category.station != normalized_row["station"]:
                    category.station = normalized_row["station"]
                    category.save(update_fields=["station"])
                    updated_categories += 1
                    self.stdout.write(f"Updated category station: {category.name} -> {category.station}")

                menu_item, item_created = MenuItem.objects.update_or_create(
                    name=normalized_row["name"],
                    defaults={
                        "category": category,
                        "price": normalized_row["price"],
                        "description": normalized_row["description"],
                        "is_available": True,
                        "deleted_at": None,
                    },
                )
                if item_created:
                    created_items += 1
                    self.stdout.write(f"Created menu item: {menu_item.name}")
                else:
                    updated_items += 1
                    self.stdout.write(f"Updated menu item: {menu_item.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completed. Categories created: {created_categories}, updated: {updated_categories}, "
                f"menu items created: {created_items}, updated: {updated_items}."
            )
        )

    def load_dataframe(self, file_path, sheet_name):
        try:
            dataframe = pd.read_excel(file_path, sheet_name=sheet_name)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Unable to read Excel file: {exc}") from exc

        dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]
        missing_columns = self.REQUIRED_COLUMNS - set(dataframe.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise CommandError(f"Missing required column(s): {missing}")

        dataframe = dataframe.where(pd.notnull(dataframe), "")
        return dataframe

    def normalize_row(self, row, row_number):
        name = str(row.get("name", "")).strip()
        category = str(row.get("category", "")).strip()
        description = str(row.get("description", "")).strip()
        station = self.normalize_station(row.get("station", ""), row_number)
        raw_price = row.get("price", "")

        if not name:
            raise CommandError(f"Row {row_number}: name is required.")
        if not category:
            raise CommandError(f"Row {row_number}: category is required.")

        try:
            price = Decimal(str(raw_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise CommandError(f"Row {row_number}: invalid price '{raw_price}'.") from exc

        if price < 0:
            raise CommandError(f"Row {row_number}: price cannot be negative.")

        return {
            "name": name,
            "category": category,
            "description": description,
            "price": price,
            "station": station,
        }

    def normalize_station(self, raw_station, row_number):
        if raw_station in (None, ""):
            return ""

        station = str(raw_station).strip().lower()
        normalized_station = self.STATION_ALIASES.get(station)
        if normalized_station is None:
            valid_values = ", ".join(sorted(self.STATION_ALIASES))
            raise CommandError(f"Row {row_number}: invalid station '{raw_station}'. Expected one of: {valid_values}.")

        return normalized_station

    def next_display_order(self):
        last_category = Category.objects.order_by("-display_order").first()
        if last_category is None:
            return 1
        return last_category.display_order + 1

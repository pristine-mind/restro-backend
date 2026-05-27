import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.menu.models import Category, MenuItem
from apps.tables.models import Table
from apps.orders.models import Order, OrderItem
from apps.billing.models import SystemSettings, Bill


class Command(BaseCommand):
    help = "Populate the database with dummy data for testing."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.create_users()
            self.create_system_settings()
            self.create_categories_and_menu_items()
            self.create_tables()
            self.create_orders_and_bills()
        self.stdout.write(self.style.SUCCESS("Dummy data created successfully!"))

    def create_users(self):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@restro.com",
                password="admin123",
                first_name="Admin",
                last_name="User",
                role="admin",
            )
            self.stdout.write("Created superuser: admin / admin123")

        staff_data = [
            {"username": "staff1", "first_name": "Ram", "last_name": "Sharma"},
            {"username": "staff2", "first_name": "Sita", "last_name": "Devi"},
            {"username": "staff3", "first_name": "Hari", "last_name": "Prasad"},
        ]
        for data in staff_data:
            if not User.objects.filter(username=data["username"]).exists():
                User.objects.create_user(
                    username=data["username"],
                    email=f"{data['username']}@restro.com",
                    password="staff123",
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role="staff",
                )
                self.stdout.write(f"Created staff: {data['username']} / staff123")

    def create_system_settings(self):
        settings, created = SystemSettings.objects.get_or_create(
            pk=1,
            defaults={
                "tax_rate": Decimal("13.00"),
                "restaurant_name": "Demo Restaurant",
                "address": "123 Demo Street, Kathmandu",
                "allow_staff_discount": True,
            },
        )
        if created:
            self.stdout.write("Created system settings.")

    def create_categories_and_menu_items(self):
        categories_data = [
            {"name": "Starters", "display_order": 1},
            {"name": "Main Course", "display_order": 2},
            {"name": "Desserts", "display_order": 3},
            {"name": "Beverages", "display_order": 4},
            {"name": "Soups", "display_order": 5},
        ]

        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={"display_order": cat_data["display_order"]},
            )
            categories[cat.name] = cat
            if created:
                self.stdout.write(f"Created category: {cat.name}")

        menu_items_data = [
            # Starters
            {"name": "Chicken Momo", "price": "250.00", "category": "Starters"},
            {"name": "Veg Spring Rolls", "price": "180.00", "category": "Starters"},
            {"name": "Buff Choila", "price": "300.00", "category": "Starters"},
            {"name": "Peanut Masala", "price": "150.00", "category": "Starters"},
            # Main Course
            {"name": "Chicken Biryani", "price": "450.00", "category": "Main Course"},
            {"name": "Veg Fried Rice", "price": "280.00", "category": "Main Course"},
            {"name": "Mutton Sekuwa", "price": "550.00", "category": "Main Course"},
            {"name": "Paneer Tikka", "price": "380.00", "category": "Main Course"},
            {"name": "Dal Bhat Tarkari", "price": "320.00", "category": "Main Course"},
            # Desserts
            {"name": "Gulab Jamun", "price": "120.00", "category": "Desserts"},
            {"name": "Rasmalai", "price": "150.00", "category": "Desserts"},
            {"name": "Ice Cream Sundae", "price": "200.00", "category": "Desserts"},
            # Beverages
            {"name": "Masala Tea", "price": "60.00", "category": "Beverages"},
            {"name": "Cold Coffee", "price": "180.00", "category": "Beverages"},
            {"name": "Fresh Lime Soda", "price": "120.00", "category": "Beverages"},
            {"name": "Mango Lassi", "price": "150.00", "category": "Beverages"},
            # Soups
            {"name": "Tomato Soup", "price": "140.00", "category": "Soups"},
            {"name": "Hot & Sour Soup", "price": "160.00", "category": "Soups"},
            {"name": "Mushroom Soup", "price": "170.00", "category": "Soups"},
        ]

        for item_data in menu_items_data:
            item, created = MenuItem.objects.get_or_create(
                name=item_data["name"],
                defaults={
                    "category": categories[item_data["category"]],
                    "price": Decimal(item_data["price"]),
                    "description": f"Delicious {item_data['name']} prepared fresh.",
                    "is_available": True,
                },
            )
            if created:
                self.stdout.write(f"Created menu item: {item.name}")

    def create_tables(self):
        tables_data = [
            {"table_number": "T1", "capacity": 2},
            {"table_number": "T2", "capacity": 2},
            {"table_number": "T3", "capacity": 4},
            {"table_number": "T4", "capacity": 4},
            {"table_number": "T5", "capacity": 6},
            {"table_number": "T6", "capacity": 6},
            {"table_number": "T7", "capacity": 8},
            {"table_number": "T8", "capacity": 10},
        ]
        for t_data in tables_data:
            table, created = Table.objects.get_or_create(
                table_number=t_data["table_number"],
                defaults={"capacity": t_data["capacity"], "status": "available"},
            )
            if created:
                self.stdout.write(f"Created table: {table.table_number} (capacity: {table.capacity})")

    def create_orders_and_bills(self):
        staff_users = list(User.objects.filter(role="staff"))
        if not staff_users:
            self.stdout.write(self.style.WARNING("No staff users found. Skipping orders."))
            return

        tables = list(Table.objects.all())
        menu_items = list(MenuItem.objects.filter(is_available=True))

        if not tables or not menu_items:
            self.stdout.write(self.style.WARNING("No tables or menu items found. Skipping orders."))
            return

        order_statuses = ["open", "billed", "paid", "cancelled"]
        payment_methods = ["cash", "card", "wallet"]
        discount_types = ["none", "percentage", "fixed"]

        # Create 10 orders with varied statuses
        for i in range(10):
            table = random.choice(tables)
            staff = random.choice(staff_users)
            status = random.choice(order_statuses)

            # For occupied tables, set status to occupied
            if status == "open":
                table.status = "occupied"
                table.save(update_fields=["status"])

            order = Order.objects.create(
                table=table,
                staff=staff,
                status=status,
                notes=f"Order #{i+1} - {random.choice(['Extra spicy', 'No onion', 'Quick service', 'Birthday celebration', ''])}",
            )

            # Add 1-5 items per order
            selected_items = random.sample(menu_items, k=random.randint(1, min(5, len(menu_items))))
            subtotal = Decimal("0.00")
            for menu_item in selected_items:
                quantity = random.randint(1, 3)
                unit_price = menu_item.price
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    unit_price=unit_price,
                )
                subtotal += unit_price * quantity

            # Create bill for billed/paid orders
            if status in ("billed", "paid"):
                tax_rate = Decimal("13.00")
                tax_amount = (subtotal * tax_rate / 100).quantize(Decimal("0.01"))

                discount_type = random.choice(discount_types)
                discount_value = Decimal("0.00")
                discount_amount = Decimal("0.00")

                if discount_type == "percentage":
                    discount_value = Decimal(str(random.choice([5, 10, 15])))
                    discount_amount = (subtotal * discount_value / 100).quantize(Decimal("0.01"))
                elif discount_type == "fixed":
                    discount_value = Decimal(str(random.choice([50, 100, 200])))
                    discount_amount = min(discount_value, subtotal)

                total = subtotal + tax_amount - discount_amount
                if total < 0:
                    total = Decimal("0.00")

                bill = Bill.objects.create(
                    order=order,
                    subtotal=subtotal,
                    tax_rate=tax_rate,
                    tax_amount=tax_amount,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    discount_amount=discount_amount,
                    total=total,
                    payment_method=random.choice(payment_methods) if status == "paid" else "cash",
                    generated_by=staff,
                )

                if status == "paid":
                    from django.utils import timezone
                    bill.paid_at = timezone.now()
                    bill.save(update_fields=["paid_at"])
                    order.closed_at = timezone.now()
                    order.save(update_fields=["closed_at"])
                    table.status = "available"
                    table.save(update_fields=["status"])

                self.stdout.write(f"Created bill for order {order.id}: Rs. {total}")

            self.stdout.write(f"Created order {order.id} with status '{status}'")

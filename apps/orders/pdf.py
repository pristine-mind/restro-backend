from django.conf import settings
from django.template.loader import render_to_string

from apps.billing.models import SystemSettings


def serialize_station_items(items: list) -> list:
    serialized_items = []
    for item in items:
        if isinstance(item, dict):
            serialized_items.append(
                {
                    "name": item.get("name", ""),
                    "quantity": item.get("quantity", 0),
                    "notes": item.get("notes", ""),
                }
            )
            continue

        serialized_items.append(
            {
                "name": item.menu_item.name,
                "quantity": item.quantity,
                "notes": item.notes,
            }
        )

    return serialized_items


def generate_station_pdf(order, station: str, items: list) -> bytes:
    """
    Renders a kitchen or bar ticket to PDF using a Django template.
    Returns raw PDF bytes.
    """
    settings_obj = SystemSettings.objects.get(pk=1)
    serialized_items = serialize_station_items(items)

    # Keep ticket width fixed at 80mm and use a conservative height estimate so
    # WeasyPrint does not spill the footer onto a second page for normal tickets.
    base_height = 105  # mm: header, separators, metadata block, footer, page margins
    item_row_height = 8
    note_row_height = 6
    padding = 12
    notes_count = sum(1 for item in serialized_items if item.get("notes"))
    page_height = base_height + (len(serialized_items) * item_row_height) + (notes_count * note_row_height) + padding

    ticket_title = "KITCHEN ORDER TICKET" if station == "kitchen" else "BAR ORDER TICKET"

    html_string = render_to_string(
        "orders/station_ticket.html",
        {
            "order": order,
            "items": serialized_items,
            "settings": settings_obj,
            "station": station,
            "ticket_title": ticket_title,
            "page_height_mm": page_height,
        },
    )

    from weasyprint import HTML

    return HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()

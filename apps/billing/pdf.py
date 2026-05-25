from django.conf import settings
from django.template.loader import render_to_string

from .models import SystemSettings


def _get_weasyprint():
    from weasyprint import CSS, HTML

    return HTML, CSS


def generate_bill_pdf(bill) -> bytes:
    """
    Renders a bill to PDF using a Django template.
    Returns raw PDF bytes.
    """
    settings_obj = SystemSettings.objects.get(pk=1)
    items = []
    for item in bill.order.items.select_related("menu_item").all():
        items.append(
            {
                "quantity": item.quantity,
                "menu_item": item.menu_item,
                "unit_price": item.unit_price,
                "notes": item.notes,
                "line_total": item.quantity * item.unit_price,
            }
        )

    html_string = render_to_string(
        "billing/bill_pdf.html",
        {
            "bill": bill,
            "order": bill.order,
            "items": items,
            "settings": settings_obj,
        },
    )

    HTML, CSS = _get_weasyprint()
    css = CSS(
        string="""
        @page { size: 80mm auto; margin: 8mm; }
        body { font-family: "Courier New", monospace; font-size: 10pt; }
        .total { font-size: 14pt; font-weight: bold; }
        .header { text-align: center; margin-bottom: 10mm; }
        .line { border-top: 1px dashed #000; margin: 4mm 0; }
        .right { text-align: right; }
        table { width: 100%; border-collapse: collapse; }
        td { padding: 2mm 0; }
    """
    )

    return HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf(stylesheets=[css])

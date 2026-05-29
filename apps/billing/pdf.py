from django.conf import settings
from django.template.loader import render_to_string

from .models import SystemSettings

_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = [
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
]


def _num_to_words_below_thousand(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    return _ONES[n // 100] + " Hundred" + (" " + _num_to_words_below_thousand(n % 100) if n % 100 else "")


def amount_in_words(amount) -> str:
    """Convert a Decimal/float to words in Nepali Rupees format."""
    try:
        from decimal import ROUND_HALF_UP, Decimal

        amount = Decimal(str(amount))
    except Exception:
        return ""

    rupees = int(amount)
    paisa = int((amount - rupees).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)

    parts = []
    if rupees > 0:
        words = []
        if rupees >= 100000:
            words.append(_num_to_words_below_thousand(rupees // 100000) + " Lakh")
            rupees %= 100000
        if rupees >= 1000:
            words.append(_num_to_words_below_thousand(rupees // 1000) + " Thousand")
            rupees %= 1000
        if rupees > 0:
            words.append(_num_to_words_below_thousand(rupees))
        parts.append("Rupees " + " ".join(words))
    else:
        parts.append("Rupees Zero")

    if paisa > 0:
        parts.append(_num_to_words_below_thousand(paisa) + " Paisa")

    return " ".join(parts) + " Only"


def generate_bill_pdf(bill) -> bytes:
    """
    Renders a bill to PDF using a Django template.
    Returns raw PDF bytes.
    """
    settings_obj = SystemSettings.get_solo()
    items = []
    for item in bill.order.items.select_related("menu_item").all():
        unit_mrp = item.unit_mrp if item.unit_mrp is not None else item.unit_price
        items.append(
            {
                "quantity": item.quantity,
                "menu_item": item.menu_item,
                "unit_price": item.unit_price,
                "unit_mrp": unit_mrp,
                "notes": item.notes,
                "line_total": item.quantity * item.unit_price,
            }
        )

    # Calculate receipt height to avoid A4 fallback
    # WeasyPrint ignores 'auto' in @page size, so we set an exact height.
    base_height = 85  # mm: header, separators, base info, totals, footer
    # Customer details add extra rows to the info table
    customer_rows = sum([
        bool(bill.customer_name),
        bool(bill.customer_address),
        bool(bill.customer_pan),
    ])
    base_height += customer_rows * 4
    item_height = 8  # mm per item (conservative: row + possible note)
    paid_stamp_height = 15 if bill.paid_at else 0
    padding = 20
    page_height = base_height + (len(items) * item_height) + paid_stamp_height + padding

    html_string = render_to_string(
        "billing/bill_pdf.html",
        {
            "bill": bill,
            "order": bill.order,
            "items": items,
            "settings": settings_obj,
            "amount_in_words": amount_in_words(bill.total),
            "page_height_mm": page_height,
        },
    )

    from weasyprint import HTML

    return HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()

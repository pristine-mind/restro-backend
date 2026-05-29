# MRP VAT Billing Implementation Guide

## Overview

This update adds a second VAT billing option inspired by standard Nepalese retail tax-invoice receipts. The system now supports two modes:

| Mode | Description | Use case |
|------|-------------|----------|
| `exclusive` (default) | Tax is added **on top** of the item price. | Restaurant bills where prices are quoted without VAT. |
| `inclusive` (new) | Tax is **already included** in the item price (MRP). The receipt reverse-calculates and shows the VAT breakdown. | Retail-style invoices where the printed/menu price is the final price the customer pays. |

In **inclusive** mode the printed receipt follows the format:

```
Gross Amount
Discount
Taxable
Nontaxable
VAT 13%
Net Amount
```

---

## Architecture Changes

### 1. Models

#### `apps/billing/models.py` – `SystemSettings`
```python
class VatMode(models.TextChoices):
    EXCLUSIVE = "exclusive", "Exclusive (tax added on top)"
    INCLUSIVE = "inclusive", "Inclusive (MRP – tax included in price)"

vat_mode = models.CharField(max_length=20, choices=VatMode.choices, default=VatMode.EXCLUSIVE)
```

Admins can still set a default mode globally via `/billing/settings/`, but the frontend is free to override it on a per-bill basis.

#### `apps/billing/models.py` – `Bill`
New fields store the breakdown at the moment the bill is generated:

| Field | Type | Meaning |
|-------|------|---------|
| `gross_amount` | Decimal | Sum of all line items (Qty × Rate) before discount. |
| `taxable_amount` | Decimal | Portion of the net amount that is subject to VAT. |
| `nontaxable_amount` | Decimal | Portion exempt from VAT (reserved for future per-item tax exemption). |
| `net_amount` | Decimal | `gross_amount - discount_amount`. |
| `vat_mode` | Char | Snapshot of `SystemSettings.vat_mode` when the bill was created. |
| `customer_name` | Char | Customer / buyer name for VAT invoice. Optional. |
| `customer_address` | Text | Customer / buyer address for VAT invoice. Optional. |
| `customer_pan` | Char | Customer PAN number for VAT invoice. Optional. |

#### `apps/menu/models.py` – `MenuItem`
```python
mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                          help_text="Maximum Retail Price (MRP). If blank, price is used.")
```

- `price` remains the actual selling price.
- `mrp` is optional. When set, it is displayed as the **Rate** on the receipt while the line total is still computed from `price`.
- If `mrp` is blank, `price` is used as the rate.

#### `apps/orders/models.py` – `OrderItem`
```python
unit_mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
```

Snapshots the MRP at order time (just like `unit_price`) so historical bills remain accurate even if menu prices change later.

---

## API Changes

### `GET /billing/settings/`
Response now includes:
```json
{
  "tax_rate": "13.00",
  "vat_mode": "inclusive",
  "restaurant_name": "My Restaurant",
  ...
}
```

### `PUT /billing/settings/`
Accepts `"vat_mode": "exclusive"` or `"vat_mode": "inclusive"`.

### `POST /billing/` (create bill)
The client can now override `vat_mode` and `tax_rate` per bill. This allows the frontend to offer **Exclusive VAT** and **Inclusive VAT** buttons that work independently of the global system setting.

```json
{
  "order": 123,
  "payment_method": "cash",
  "discount_type": "none",
  "discount_value": 0,
  "vat_mode": "inclusive",
  "tax_rate": "13.00",
  "customer_name": "Tranquility Paradise Pvt. Ltd.",
  "customer_address": "Gokarna",
  "customer_pan": "619724393"
}
```

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `order` | ✅ | — | Order ID to bill. |
| `payment_method` | ✅ | — | `cash`, `card`, `wallet`, `esewa`. |
| `discount_type` | ❌ | `none` | `none`, `percentage`, `fixed`. |
| `discount_value` | ❌ | `0` | — |
| `vat_mode` | ❌ | System setting | `"exclusive"` or `"inclusive"`. |
| `tax_rate` | ❌ | System setting | e.g. `"13.00"`. |
| `customer_name` | ❌ | `""` | — |
| `customer_address` | ❌ | `""` | — |
| `customer_pan` | ❌ | `""` | — |

### `GET /billing/<id>/`
Response now includes the new breakdown fields:
```json
{
  "id": 42,
  "subtotal": "715.00",
  "gross_amount": "715.00",
  "tax_rate": "13.00",
  "vat_mode": "inclusive",
  "tax_amount": "74.78",
  "taxable_amount": "575.22",
  "nontaxable_amount": "0.00",
  "discount_amount": "65.00",
  "net_amount": "650.00",
  "total": "650.00",
  "customer_name": "Tranquility Paradise Pvt. Ltd.",
  "customer_address": "Gokarna",
  "customer_pan": "619724393",
  ...
}
```

### `GET /billing/<id>/pdf/`
The thermal receipt PDF renders a different totals section depending on `vat_mode`:
- **Exclusive** → old format (`Subtotal → Discount → Tax → TOTAL`).
- **Inclusive** → new MRP format (`Gross Amount → Discount → Taxable → Nontaxable → VAT → Net Amount`).

---

## Calculation Logic

### Exclusive Mode (existing)
```
subtotal      = Σ(quantity × unit_price)
discount      = calculated from subtotal
taxable       = subtotal - discount
tax_amount    = taxable × tax_rate / 100
total         = taxable + tax_amount
```

### Inclusive Mode (new)
```
subtotal      = Σ(quantity × unit_price)
gross_amount  = subtotal
discount      = calculated from subtotal
net_amount    = gross_amount - discount

# Reverse-calculate VAT because it is already embedded in the prices
taxable_amount = net_amount / (1 + tax_rate / 100)
tax_amount     = net_amount - taxable_amount
nontaxable_amount = 0
total          = net_amount
```

**Example** (13 % VAT, subtotal = 715.00, discount = 65.00):
```
net_amount     = 715.00 - 65.00            = 650.00
taxable_amount = 650.00 / 1.13             = 575.22
tax_amount     = 650.00 - 575.22           =  74.78
total          = 650.00
```

---

## PDF Receipt Format

### Exclusive mode (unchanged)
```
Item                Qty   Price    Amt
--------------------------------
Subtotal                     XXX.XX
Discount                     -XX.XX
Tax (13%)                     XX.XX
TOTAL                        XXX.XX
```

### Inclusive mode (new)
```
Item                Qty   Rate     Amt
--------------------------------
Gross Amount                 XXX.XX
Discount                     -XX.XX
Taxable                      XXX.XX
Nontaxable                   XXX.XX
VAT (13%)                    XXX.XX
Net Amount                   XXX.XX
```

The **Rate** column shows `unit_mrp` (falls back to `unit_price` when MRP is not set).

---

## Database Migrations

Three new migrations were generated:

| App | Migration | Change |
|-----|-----------|--------|
| `billing` | `0005_bill_gross_amount_bill_net_amount_and_more.py` | Adds `gross_amount`, `net_amount`, `taxable_amount`, `nontaxable_amount`, `vat_mode` to `Bill`; adds `vat_mode` to `SystemSettings`. |
| `menu` | `0003_menuitem_mrp.py` | Adds optional `mrp` field to `MenuItem`. |
| `orders` | `0005_orderitem_unit_mrp.py` | Adds `unit_mrp` snapshot field to `OrderItem`. |

Apply with:
```bash
python manage.py migrate
```

| App | Migration | Change |
|-----|-----------|--------|
| `billing` | `0006_bill_customer_address_bill_customer_name_and_more.py` | Adds `customer_name`, `customer_address`, `customer_pan` to `Bill`. |

---

## Backward Compatibility

- **Default mode** is `exclusive`, so existing behaviour is preserved until an admin explicitly switches to `inclusive`.
- Existing bills have `vat_mode = "exclusive"` (default) and will continue to render with the old receipt format.
- `mrp` is optional; if blank, `price` is used seamlessly.

---

## Frontend Integration Notes

1. **Settings page** – add a dropdown for `vat_mode` (`exclusive` / `inclusive`) in the system-settings form.
2. **Menu management** – optionally expose the `mrp` field when creating/editing menu items.
3. **Bill detail / preview** – when displaying a bill, check `bill.vat_mode`:
   - `"exclusive"` → show `Subtotal`, `Tax`, `TOTAL`.
   - `"inclusive"` → show `Gross Amount`, `Taxable`, `Nontaxable`, `VAT`, `Net Amount`.
4. **Reports** – `DailyReportView` and `ItemPopularityReportView` use `total` and `unit_price`, which remain valid in both modes.

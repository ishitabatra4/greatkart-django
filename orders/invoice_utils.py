
from decimal import Decimal, ROUND_HALF_UP

from .models import OrderProduct, VendorInvoice


CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value or 0)).quantize(
        CENT,
        rounding=ROUND_HALF_UP
    )


def generate_vendor_invoices(order):
    """
    Generate one invoice per vendor for an order.
    All products belonging to the same vendor are grouped
    into one invoice.
    """

    order_items = list(
        OrderProduct.objects
        .filter(order=order, ordered=True)
        .select_related("product", "product__vendor")
        .prefetch_related("variations")
        .order_by("id")
    )

    if not order_items:
        return []

    # Group items by vendor. Products without a vendor
    # are grouped into one platform/unassigned invoice.
    grouped_items = {}

    for item in order_items:
        vendor = item.product.vendor
        vendor_id = vendor.pk if vendor else None

        if vendor_id not in grouped_items:
            grouped_items[vendor_id] = {
                "vendor": vendor,
                "items": [],
                "subtotal": Decimal("0.00"),
            }

        line_total = money(
            Decimal(str(item.product_price)) * item.quantity
        )

        grouped_items[vendor_id]["items"].append(item)
        grouped_items[vendor_id]["subtotal"] += line_total

    groups = list(grouped_items.values())

    order_tax = money(order.tax)
    combined_subtotal = sum(
        (group["subtotal"] for group in groups),
        Decimal("0.00")
    )

    # Allocate the order tax proportionally across vendors.
    allocated_tax = Decimal("0.00")

    for index, group in enumerate(groups):
        if index == len(groups) - 1:
            # Assign rounding remainder to the last invoice.
            group["tax"] = order_tax - allocated_tax
        elif combined_subtotal > 0:
            group["tax"] = money(
                order_tax * group["subtotal"] / combined_subtotal
            )
            allocated_tax += group["tax"]
        else:
            group["tax"] = Decimal("0.00")

    invoices = []

    for group in groups:
        vendor = group["vendor"]

        # Reuse an existing invoice for this order/vendor,
        # instead of creating duplicates on repeated calls.
        invoice = VendorInvoice.objects.filter(
            order=order,
            vendor=vendor
        ).first()

        if invoice is None:
            vendor_code = str(vendor.pk) if vendor else "PLATFORM"
            invoice_number = (
                f"INV-{order.order_number}-{vendor_code}"
            )

            invoice = VendorInvoice.objects.create(
                order=order,
                vendor=vendor,
                invoice_number=invoice_number,
                subtotal=group["subtotal"],
                tax=group["tax"],
                total=group["subtotal"] + group["tax"],
                status="New",
            )
        else:
            invoice.subtotal = group["subtotal"]
            invoice.tax = group["tax"]
            invoice.total = group["subtotal"] + group["tax"]
            invoice.save(
                update_fields=[
                    "subtotal",
                    "tax",
                    "total",
                    "updated_at",
                ]
            )

        # Link every line item to its vendor's invoice.
        for item in group["items"]:
            if item.vendor_invoice_id != invoice.pk:
                item.vendor_invoice = invoice
                item.save(update_fields=["vendor_invoice"])

        invoices.append(invoice)

    return invoices

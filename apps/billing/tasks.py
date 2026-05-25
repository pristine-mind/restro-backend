from celery import shared_task

from .pdf import generate_bill_pdf


@shared_task
def generate_bill_pdf_task(bill_id):
    """Async task to generate a bill PDF."""
    from .models import Bill

    bill = Bill.objects.get(pk=bill_id)
    return generate_bill_pdf(bill)

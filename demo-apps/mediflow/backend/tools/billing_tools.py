"""Billing tool wrappers for the Strands agent."""

from strands import tool
from backend.services import billing_service


@tool
def get_outstanding_invoices(patient_id: str = "") -> list:
    """List outstanding (unpaid) invoices, optionally filtered by patient.

    Args:
        patient_id: Optional patient ID to filter by. If empty, returns all outstanding invoices.
    """
    return billing_service.get_outstanding_invoices(patient_id or None)


@tool
def get_invoice(invoice_id: str) -> dict:
    """Get full details of a specific invoice including patient info.

    Args:
        invoice_id: Invoice ID (e.g. 'inv-001')
    """
    return billing_service.get_invoice(invoice_id)


@tool
def record_payment(invoice_id: str, amount: float) -> dict:
    """Record a payment against an invoice. Automatically marks as paid if fully settled.

    Args:
        invoice_id: Invoice ID to apply the payment to (e.g. 'inv-001')
        amount: Payment amount in dollars (e.g. 85.00)
    """
    return billing_service.record_payment(invoice_id, amount)


@tool
def send_payment_reminder(invoice_id: str) -> dict:
    """Send a payment reminder/chase to the patient for an outstanding invoice.

    Args:
        invoice_id: Invoice ID to send the reminder for (e.g. 'inv-001')
    """
    return billing_service.send_payment_chase(invoice_id)

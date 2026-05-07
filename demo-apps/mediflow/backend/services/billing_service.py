"""Billing and invoice management service."""

import uuid
from datetime import datetime

from backend.services.database import query_db, execute_db


def get_outstanding_invoices(patient_id: str = None) -> list:
    """List all outstanding invoices, optionally filtered by patient.

    Joins with patients table for display names.
    """
    sql = """
        SELECT i.*,
               p.first_name || ' ' || p.last_name AS patient_name
        FROM invoices i
        JOIN patients p ON i.patient_id = p.id
        WHERE i.status = 'outstanding'
    """
    params: list = []

    if patient_id:
        sql += " AND i.patient_id = ?"
        params.append(patient_id)

    sql += " ORDER BY i.due_date ASC"
    return query_db(sql, tuple(params))


def get_invoice(invoice_id: str) -> dict:
    """Return a single invoice with patient information."""
    rows = query_db(
        """SELECT i.*,
                  p.first_name || ' ' || p.last_name AS patient_name,
                  p.phone AS patient_phone,
                  p.email AS patient_email
           FROM invoices i
           JOIN patients p ON i.patient_id = p.id
           WHERE i.id = ?""",
        (invoice_id,),
    )
    if not rows:
        return {"error": "Invoice not found", "invoice_id": invoice_id}
    return rows[0]


def record_payment(invoice_id: str, amount: float) -> dict:
    """Record a payment against an invoice.

    If the cumulative amount_paid reaches or exceeds the invoice amount
    the status is automatically set to 'paid'.

    Returns:
        The updated invoice dict.
    """
    invoice = get_invoice(invoice_id)
    if "error" in invoice:
        return invoice

    new_paid = (invoice.get("amount_paid") or 0) + amount
    new_status = "paid" if new_paid >= invoice["amount"] else "outstanding"

    execute_db(
        "UPDATE invoices SET amount_paid = ?, status = ? WHERE id = ?",
        (new_paid, new_status, invoice_id),
    )

    return get_invoice(invoice_id)


def send_payment_chase(invoice_id: str) -> dict:
    """Send a payment-chase communication for an outstanding invoice.

    Increments chase_count, updates last_chased, and creates a
    communications record with the chase message.

    Returns:
        Dict with the updated invoice and the communication record.
    """
    invoice = get_invoice(invoice_id)
    if "error" in invoice:
        return invoice

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_chase_count = (invoice.get("chase_count") or 0) + 1

    execute_db(
        "UPDATE invoices SET chase_count = ?, last_chased = ? WHERE id = ?",
        (new_chase_count, now, invoice_id),
    )

    # Build chase message
    outstanding = invoice["amount"] - (invoice.get("amount_paid") or 0)
    message = (
        f"Payment reminder: Invoice {invoice_id} has an outstanding balance of "
        f"${outstanding:.2f}. Due date: {invoice.get('due_date', 'N/A')}. "
        f"Please arrange payment at your earliest convenience."
    )

    comm_id = f"comm-{uuid.uuid4().hex[:8]}"
    patient_id = invoice["patient_id"]

    # Determine channel from patient preferences
    patients = query_db("SELECT preferred_contact FROM patients WHERE id = ?", (patient_id,))
    channel = patients[0]["preferred_contact"] if patients else "phone"

    execute_db(
        """INSERT INTO communications (id, patient_id, channel, type, content, triggered_by)
           VALUES (?, ?, ?, 'payment_chase', ?, 'billing_service')""",
        (comm_id, patient_id, channel, message),
    )

    updated_invoice = get_invoice(invoice_id)
    communication = query_db("SELECT * FROM communications WHERE id = ?", (comm_id,))

    return {
        "invoice": updated_invoice,
        "communication": communication[0] if communication else None,
    }

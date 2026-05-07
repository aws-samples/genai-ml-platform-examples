"""Patient record management service."""

from backend.services.database import query_db, execute_db


def search_patients(query: str) -> list:
    """Search patients by first / last / full name (case-insensitive).

    Splits the query on whitespace and requires every token to match
    somewhere in ``first_name || ' ' || last_name``. Falls back to a
    plain LIKE on that same concatenation so single-token queries
    still behave the same way.

    Args:
        query: Search string. Single token (e.g. "Sarah") or full
            name (e.g. "Sarah Mitchell").

    Returns:
        List of matching patient dicts.
    """
    tokens = [t for t in (query or "").split() if t]
    if not tokens:
        return []

    # Build: (first_name || ' ' || last_name) LIKE ? AND ... AND ... ORDER BY ...
    where = " AND ".join(
        ["(first_name || ' ' || last_name) LIKE ?"] * len(tokens)
    )
    params = tuple(f"%{t}%" for t in tokens)
    return query_db(
        f"""SELECT * FROM patients
            WHERE {where}
            ORDER BY last_name, first_name""",  # nosec B608 - where built from LIKE ? clauses
        params,
    )


def get_patient(patient_id: str) -> dict:
    """Return a full patient record by ID."""
    rows = query_db("SELECT * FROM patients WHERE id = ?", (patient_id,))
    if not rows:
        return {"error": "Patient not found", "patient_id": patient_id}
    return rows[0]


def get_patient_history(patient_id: str) -> dict:
    """Return a patient record together with recent appointments and invoices."""
    patient = get_patient(patient_id)
    if "error" in patient:
        return patient

    appointments = query_db(
        """SELECT a.*, d.name AS doctor_name
           FROM appointments a
           JOIN doctors d ON a.doctor_id = d.id
           WHERE a.patient_id = ?
           ORDER BY a.date DESC, a.time DESC
           LIMIT 20""",
        (patient_id,),
    )

    invoices = query_db(
        """SELECT * FROM invoices
           WHERE patient_id = ?
           ORDER BY issued_date DESC
           LIMIT 20""",
        (patient_id,),
    )

    return {
        **patient,
        "appointments": appointments,
        "invoices": invoices,
    }


def update_patient_notes(patient_id: str, notes: str) -> dict:
    """Append to a patient's existing notes (does not replace).

    Returns:
        The updated patient dict.
    """
    # Append rather than overwrite
    execute_db(
        """UPDATE patients
           SET notes = CASE
               WHEN notes IS NULL OR notes = '' THEN ?
               ELSE notes || '\n' || ?
           END
           WHERE id = ?""",
        (notes, notes, patient_id),
    )

    return get_patient(patient_id)

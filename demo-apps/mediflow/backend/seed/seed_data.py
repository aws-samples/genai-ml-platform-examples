"""Load seed data fixtures into the SQLite database."""

import json
import random
from datetime import datetime, timedelta, date
from pathlib import Path

from backend.services.database import get_connection, init_db

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    """Load a JSON fixture file from the fixtures directory."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# Day name lookup for Python weekday() → string
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def generate_appointments(doctors: list, patients: list, start_date: date, end_date: date, seed: int = 42) -> list:
    """Programmatically generate realistic appointment data across a date range.

    Respects each doctor's working_days, hours, and consultation_duration.
    Produces a diverse, realistic distribution of appointments.
    Pediatric patients (under 16) are always assigned to the paediatrics doctor.
    """
    rng = random.Random(seed)

    # Identify pediatric patients (under 16 as of start_date)
    def _age_at(dob_str, ref):
        dob = date.fromisoformat(dob_str)
        return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

    paed_doctor = next((d for d in doctors if d.get("specialty") == "Paediatrics"), None)
    paed_patient_ids = {p["id"] for p in patients if _age_at(p["dob"], start_date) < 16}
    non_paed_patient_ids = [p["id"] for p in patients if p["id"] not in paed_patient_ids]
    paed_patient_ids_list = list(paed_patient_ids)

    patient_ids = [p["id"] for p in patients]

    # Appointment type weights
    apt_types = ["standard", "follow_up", "urgent", "telehealth", "new_patient"]
    apt_type_weights = [0.45, 0.25, 0.05, 0.15, 0.10]

    # Build per-doctor slot templates
    doctor_slots = {}
    for doc in doctors:
        working_days = doc.get("working_days", [])
        h_start = doc.get("hours_start", "09:00")
        h_end = doc.get("hours_end", "17:00")
        duration = doc.get("consultation_duration_mins", 30)

        start_h, start_m = map(int, h_start.split(":"))
        end_h, end_m = map(int, h_end.split(":"))
        start_mins = start_h * 60 + start_m
        end_mins = end_h * 60 + end_m

        slots = []
        t = start_mins
        while t + duration <= end_mins:
            h, m = divmod(t, 60)
            slots.append(f"{h:02d}:{m:02d}")
            t += 30  # always 30-min grid

        doctor_slots[doc["id"]] = {
            "working_days": set(working_days),
            "slots": slots,
            "duration": duration,
        }

    today = date.today()
    appointments = []
    apt_counter = 100  # start IDs after fixture range

    current = start_date
    while current <= end_date:
        day_name = _WEEKDAY_NAMES[current.weekday()]

        # Skip weekends
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        for doc in doctors:
            doc_id = doc["id"]
            info = doctor_slots[doc_id]

            if day_name not in info["working_days"]:
                continue

            available_slots = list(info["slots"])

            # Fill rate: 60-85% of available slots on any given day
            fill_count = rng.randint(
                int(len(available_slots) * 0.60),
                int(len(available_slots) * 0.85),
            )
            fill_count = max(1, min(fill_count, len(available_slots)))

            chosen_slots = rng.sample(available_slots, fill_count)
            chosen_slots.sort()

            for time_slot in chosen_slots:
                apt_counter += 1

                # Pediatric patients only see the paediatrics doctor
                if paed_doctor and doc_id == paed_doctor["id"] and paed_patient_ids_list:
                    pat_id = rng.choice(paed_patient_ids_list)
                elif doc_id == (paed_doctor["id"] if paed_doctor else None):
                    pat_id = rng.choice(patient_ids)
                else:
                    pat_id = rng.choice(non_paed_patient_ids if non_paed_patient_ids else patient_ids)

                apt_type = rng.choices(apt_types, weights=apt_type_weights, k=1)[0]

                # Status depends on whether appointment is past/future
                if current < today:
                    status = rng.choices(
                        ["completed", "no-show", "cancelled"],
                        weights=[0.82, 0.08, 0.10],
                        k=1,
                    )[0]
                elif current == today:
                    status = rng.choices(
                        ["scheduled", "completed"],
                        weights=[0.6, 0.4],
                        k=1,
                    )[0]
                else:
                    status = rng.choices(
                        ["scheduled", "cancelled"],
                        weights=[0.92, 0.08],
                        k=1,
                    )[0]

                appointments.append({
                    "id": f"apt-gen-{apt_counter:05d}",
                    "patient_id": pat_id,
                    "doctor_id": doc_id,
                    "date": current.isoformat(),
                    "time": time_slot,
                    "duration_mins": info["duration"],
                    "status": status,
                    "type": apt_type,
                    "reminder_sent": 1 if current <= today else 0,
                    "created_at": (current - timedelta(days=rng.randint(1, 14))).isoformat() + "T09:00:00",
                    "notes": "",
                })

        current += timedelta(days=1)

    return appointments


def _next_working_day(d: date, doctor: dict) -> date:
    """Advance date to the next day the doctor works."""
    working_days = set(doctor.get("working_days", []))
    for _ in range(14):  # safety limit
        if _WEEKDAY_NAMES[d.weekday()] in working_days:
            return d
        d += timedelta(days=1)
    return d


def _make_appointment(counter: int, patient_id: str, doctor_id: str, apt_date: date,
                      time: str, duration: int, status: str, apt_type: str,
                      reminder_sent: bool, notes: str = "") -> dict:
    """Build a single appointment dict with apt-pat-NNNNN ID scheme."""
    return {
        "id": f"apt-pat-{counter:05d}",
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "date": apt_date.isoformat(),
        "time": time,
        "duration_mins": duration,
        "status": status,
        "type": apt_type,
        "reminder_sent": 1 if reminder_sent else 0,
        "created_at": (apt_date - timedelta(days=7)).isoformat() + "T09:00:00",
        "notes": notes,
    }


def generate_patterned_appointments(patients: list, doctors: list,
                                    start_date: date, end_date: date) -> list:
    """Generate appointments with discoverable patterns for the analysis pipeline.

    Creates structured appointment data alongside the random generation so that
    the pipeline can organically discover:
    - Chronic condition cascades (blood test → review → medication adjustment)
    - Day-of-week cancellation patterns
    - Pediatric patients always with Dr Kim
    - New patient → 2-week follow-up sequences
    - No-show clustering on early morning slots
    """
    appointments = []
    counter = 0
    today = date.today()

    doctor_map = {d["id"]: d for d in doctors}
    patient_map = {p["id"]: p for p in patients}

    def _status_for(apt_date):
        return "completed" if apt_date < today else "scheduled"

    # ── Chronic condition cascades ──
    # Each chronic patient gets 2-3 quarterly (or 6-weekly) cycles:
    #   Stage 1: blood_test (morning) → Stage 2: follow_up review (4-7 days) → Stage 3: standard medication review (2 weeks)
    chronic_config = [
        ("pat-004", "dr-chen", 12),   # Asthma — 3-monthly
        ("pat-009", "dr-chen", 12),   # Type 2 diabetes — quarterly
        ("pat-042", "dr-chen", 6),    # Rheumatoid arthritis — 6-weekly
        ("pat-043", "dr-patel", 12),  # COPD — quarterly
        ("pat-039", "dr-kim", 12),    # Type 1 diabetes (paediatric) — quarterly
    ]

    for pat_id, doc_id, cycle_weeks in chronic_config:
        doc = doctor_map[doc_id]
        rng = random.Random(hash(pat_id) + 42)
        cycle_start = start_date + timedelta(days=rng.randint(0, 10))

        for cycle_num in range(4):
            test_date = cycle_start + timedelta(weeks=cycle_weeks * cycle_num)
            test_date = _next_working_day(test_date, doc)
            if test_date > end_date:
                break

            # Stage 1: Fasting blood test (morning slot)
            counter += 1
            appointments.append(_make_appointment(
                counter, pat_id, doc_id, test_date, "09:00",
                doc["consultation_duration_mins"], _status_for(test_date),
                "blood_test", test_date <= today,
                "Fasting blood test — part of regular monitoring cycle"
            ))

            # Stage 2: Results review 4-7 days later
            review_date = test_date + timedelta(days=rng.choice([4, 5, 6, 7]))
            review_date = _next_working_day(review_date, doc)
            if review_date > end_date:
                continue

            counter += 1
            appointments.append(_make_appointment(
                counter, pat_id, doc_id, review_date,
                rng.choice(["10:00", "10:30", "11:00"]),
                doc["consultation_duration_mins"], _status_for(review_date),
                "follow_up", review_date <= today,
                "Results review — follow-up from blood test"
            ))

            # Stage 3: Medication review 2 weeks after results
            med_date = review_date + timedelta(days=14)
            med_date = _next_working_day(med_date, doc)
            if med_date > end_date:
                continue

            counter += 1
            appointments.append(_make_appointment(
                counter, pat_id, doc_id, med_date,
                rng.choice(["14:00", "14:30", "15:00"]),
                doc["consultation_duration_mins"], _status_for(med_date),
                "standard", med_date <= today,
                "Medication review — cycle follow-up"
            ))

    # ── Day-of-week cancellation patterns ──
    # These patients consistently cancel/no-show on a specific weekday.
    # The pattern is NOT mentioned in their notes — it must be discovered from data.
    # We use a longer lookback (Oct 2025) so there's enough historical data to detect.
    dow_history_start = date(2025, 10, 1)
    dow_config = [
        ("pat-044", 4, "dr-chen"),    # Tanya Marsh — cancels Fridays
        ("pat-045", 0, "dr-patel"),   # Damien Foster — cancels Mondays
        ("pat-007", 2, "dr-chen"),    # James Cooper — misses Wednesdays
    ]

    for pat_id, cancel_weekday, doc_id in dow_config:
        doc = doctor_map[doc_id]
        rng = random.Random(hash(pat_id) + 77)
        slots = ["09:00", "09:30", "10:00", "11:00", "14:00", "15:00"]

        # Generate ~bi-weekly appointments on the target day going back 6 months
        # Plus some normal-day appointments for contrast
        current = dow_history_start
        while current <= end_date:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue

            if _WEEKDAY_NAMES[current.weekday()] not in set(doc.get("working_days", [])):
                current += timedelta(days=1)
                continue

            if current.weekday() == cancel_weekday:
                # Book on the problem day roughly every 2-3 weeks
                if rng.random() < 0.45:
                    counter += 1
                    if current < today:
                        # 85% cancel/no-show on this day
                        status = rng.choices(
                            ["cancelled", "no-show", "completed"],
                            weights=[0.50, 0.35, 0.15], k=1
                        )[0]
                    else:
                        status = "scheduled"
                    appointments.append(_make_appointment(
                        counter, pat_id, doc_id, current,
                        rng.choice(slots), doc["consultation_duration_mins"],
                        status, "standard", current <= today
                    ))
            else:
                # Occasionally book on other days — normal completion rate
                if rng.random() < 0.06:
                    counter += 1
                    status = "completed" if current < today else "scheduled"
                    appointments.append(_make_appointment(
                        counter, pat_id, doc_id, current,
                        rng.choice(slots), doc["consultation_duration_mins"],
                        status, "standard", current <= today
                    ))

            current += timedelta(days=1)

    # ── Pediatric guardian notes ──
    # Add a few explicit pediatric appointments with guardian accompaniment notes
    paed_doctor = doctor_map.get("dr-kim")
    if paed_doctor:
        guardian_notes = {
            "pat-021": "Accompanied by mum Jenny Walsh",
            "pat-025": "Accompanied by father Wei Zhang",
            "pat-028": "Accompanied by mum Kate Stewart",
            "pat-033": "Accompanied by dad Sam Campbell",
            "pat-036": "Accompanied by mum Sarah Mitchell",
            "pat-037": "Accompanied by mum Sarah Mitchell",
            "pat-038": "Accompanied by mum Riya Kapoor",
            "pat-039": "Accompanied by dad Mark Barnes",
        }
        rng = random.Random(99)
        for pat_id, guardian_note in guardian_notes.items():
            # Generate 3-4 appointments per pediatric patient
            apt_date = start_date + timedelta(days=rng.randint(0, 14))
            for _ in range(rng.randint(3, 4)):
                apt_date = _next_working_day(apt_date, paed_doctor)
                if apt_date > end_date:
                    break
                counter += 1
                appointments.append(_make_appointment(
                    counter, pat_id, "dr-kim", apt_date,
                    rng.choice(["09:00", "09:45", "10:30", "11:15", "13:00", "13:45"]),
                    45, _status_for(apt_date),
                    rng.choice(["standard", "follow_up"]),
                    apt_date <= today, guardian_note
                ))
                apt_date += timedelta(weeks=rng.randint(4, 8))

    # ── New patient → 2-week follow-up sequences ──
    # For patients with null or recent last_visit, create new_patient → follow_up pairs
    new_patient_candidates = [
        ("pat-027", "dr-patel"),  # Jasmine Kaur — new patient, transferred from Melbourne
        ("pat-024", "dr-chen"),   # Nina Petrova — sparse notes, treat as recent-ish
    ]
    rng = random.Random(55)
    for pat_id, doc_id in new_patient_candidates:
        doc = doctor_map[doc_id]
        initial_date = start_date + timedelta(days=rng.randint(3, 21))
        initial_date = _next_working_day(initial_date, doc)
        if initial_date > end_date:
            continue

        # Initial new_patient appointment
        counter += 1
        appointments.append(_make_appointment(
            counter, pat_id, doc_id, initial_date,
            rng.choice(["09:30", "10:00", "11:00"]),
            doc["consultation_duration_mins"], _status_for(initial_date),
            "new_patient", initial_date <= today,
            "New patient initial consultation"
        ))

        # Follow-up 2 weeks later
        followup_date = initial_date + timedelta(days=14)
        followup_date = _next_working_day(followup_date, doc)
        if followup_date <= end_date:
            counter += 1
            appointments.append(_make_appointment(
                counter, pat_id, doc_id, followup_date,
                rng.choice(["10:30", "14:00", "14:30"]),
                doc["consultation_duration_mins"], _status_for(followup_date),
                "follow_up", followup_date <= today,
                "2-week follow-up from initial consultation"
            ))

    # Also scan random appointments for new_patient type and add follow-ups later
    # (handled by the pipeline discovering the pattern from existing data)

    # ── No-show clustering on early morning slots ──
    # High no-show patients miss early morning appointments disproportionately.
    # Use longer lookback for enough data points.
    noshow_history_start = date(2025, 10, 1)
    noshow_config = [
        ("pat-049", "dr-chen", 5),   # Marcus Webb — 5 no-shows
        ("pat-050", "dr-patel", 4),  # Jade Holloway — 4 no-shows
        ("pat-030", "dr-chen", 3),   # Ethan Williams — 3 no-shows
    ]

    for pat_id, doc_id, target_noshows in noshow_config:
        doc = doctor_map[doc_id]
        rng = random.Random(hash(pat_id) + 123)
        early_slots = ["09:00", "09:30"]
        later_slots = ["11:00", "14:00", "15:00"]
        noshows_placed = 0

        # Generate appointments every 2-3 weeks going back to Oct 2025
        apt_date = noshow_history_start + timedelta(days=rng.randint(0, 7))
        while apt_date < today:
            apt_date = _next_working_day(apt_date, doc)
            if apt_date >= today:
                break

            counter += 1
            if noshows_placed < target_noshows:
                # Early morning no-show
                appointments.append(_make_appointment(
                    counter, pat_id, doc_id, apt_date,
                    rng.choice(early_slots), doc["consultation_duration_mins"],
                    "no-show", True,
                    "standard", True
                ))
                noshows_placed += 1
            else:
                # Later slot, completed normally
                appointments.append(_make_appointment(
                    counter, pat_id, doc_id, apt_date,
                    rng.choice(later_slots), doc["consultation_duration_mins"],
                    "completed", True,
                    "standard", True
                ))

            apt_date += timedelta(days=rng.randint(14, 28))

    return appointments


def seed_all():
    """Load all domain fixtures into the database."""
    init_db()
    conn = get_connection()

    # Doctors
    doctors = load_fixture("doctors.json")
    for d in doctors:
        conn.execute(
            "INSERT OR REPLACE INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["name"], d["specialty"], d["consultation_duration_mins"], json.dumps(d["working_days"]), d["hours_start"], d["hours_end"]),
        )

    # Patients
    patients = load_fixture("patients.json")
    for p in patients:
        conn.execute(
            "INSERT OR REPLACE INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count, last_visit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p["id"], p["first_name"], p["last_name"], p["dob"], p["phone"], p["email"], p["preferred_contact"], p.get("notes", ""), p.get("no_show_count", 0), p.get("last_visit")),
        )

    # Appointments — load fixtures first, then generate extended data
    appointments = load_fixture("appointments.json")
    for a in appointments:
        conn.execute(
            "INSERT OR REPLACE INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent, created_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a["id"], a["patient_id"], a["doctor_id"], a["date"], a["time"], a.get("duration_mins", 30), a.get("status", "scheduled"), a.get("type", "standard"), a.get("reminder_sent", 0), a.get("created_at", "2026-03-08T09:00:00"), a.get("notes", "")),
        )

    # Generate 6 months of extended appointment data (Mar 14 → Sep 30 2026)
    generated = generate_appointments(
        doctors=doctors,
        patients=patients,
        start_date=date(2026, 3, 14),
        end_date=date(2026, 9, 30),
    )
    for a in generated:
        conn.execute(
            "INSERT OR REPLACE INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent, created_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a["id"], a["patient_id"], a["doctor_id"], a["date"], a["time"], a["duration_mins"], a["status"], a["type"], a["reminder_sent"], a["created_at"], a["notes"]),
        )

    # Generate patterned appointments (chronic cascades, day-of-week cancellations, etc.)
    patterned = generate_patterned_appointments(
        patients=patients,
        doctors=doctors,
        start_date=date(2026, 3, 14),
        end_date=date(2026, 9, 30),
    )
    for a in patterned:
        conn.execute(
            "INSERT OR REPLACE INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent, created_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a["id"], a["patient_id"], a["doctor_id"], a["date"], a["time"], a["duration_mins"], a["status"], a["type"], a["reminder_sent"], a["created_at"], a["notes"]),
        )

    # Invoices
    invoices = load_fixture("invoices.json")
    for inv in invoices:
        conn.execute(
            "INSERT OR REPLACE INTO invoices (id, patient_id, appointment_id, amount, amount_paid, status, due_date, issued_date, chase_count, last_chased, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inv["id"], inv["patient_id"], inv.get("appointment_id"), inv["amount"], inv.get("amount_paid", 0), inv.get("status", "outstanding"), inv.get("due_date"), inv.get("issued_date"), inv.get("chase_count", 0), inv.get("last_chased"), inv.get("description", "")),
        )

    # Practice info
    practice = load_fixture("practice_info.json")
    for key, value in practice.items():
        conn.execute("INSERT OR REPLACE INTO practice_info (key, value) VALUES (?, ?)", (key, value))

    # Pathology results (dates anchored to today so Morning Briefing always has data)
    pathology = load_fixture("pathology_results.json")
    today_str = date.today().isoformat()
    for pr in pathology:
        received_date = today_str if pr["received_date"] == "__TODAY__" else pr["received_date"]
        conn.execute(
            "INSERT OR REPLACE INTO pathology_results "
            "(id, patient_id, test_name, result_value, reference_range, flagged, flag_reason, "
            "ordering_doctor_id, received_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pr["id"], pr["patient_id"], pr["test_name"], pr["result_value"],
             pr.get("reference_range"), pr.get("flagged", 0), pr.get("flag_reason"),
             pr.get("ordering_doctor_id"), received_date),
        )

    conn.commit()
    conn.close()
    print(f"Seeded: {len(doctors)} doctors, {len(patients)} patients, {len(appointments)} fixture + {len(generated)} generated + {len(patterned)} patterned appointments, {len(invoices)} invoices, {len(practice)} practice info entries, {len(pathology)} pathology results")

    # Hand-seeded communications for demo variety (runs after conn is closed so it manages its own)
    load_communications_fixtures()


def load_communications_fixtures():
    """Load hand-seeded communications for demo variety.

    These entries sit alongside the auto-generated reminders produced by
    comms_service; their timestamps are more recent so they sort to the top
    of /api/data/comms. `triggered_by` drives direction inference at the API
    layer (see data_routes.list_comms).
    """
    fixture_path = FIXTURES_DIR / "communications.json"
    if not fixture_path.exists():
        print("No communications fixture found — skipping")
        return

    with open(fixture_path) as f:
        entries = json.load(f)

    conn = get_connection()
    for c in entries:
        conn.execute(
            """INSERT OR REPLACE INTO communications
               (id, patient_id, channel, type, content, status, sent_at, triggered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c["id"],
                c["patient_id"],
                c["channel"],
                c.get("type"),
                c.get("content"),
                c.get("status", "sent"),
                c["sent_at"],
                c.get("triggered_by"),
            ),
        )

    conn.commit()
    conn.close()
    print(f"Loaded communications: {len(entries)} hand-seeded entries")


def _ensure_demo_affected_count(conn, rows, today_iso):
    """Normalise today's Dr Patel appointments to 11 scheduled so the
    sick-day demo moment always reads the same. The fixture used to gate
    this on a seeded unavailability row for Patel; we now run unconditionally
    because the demo lands the conflict via an agent tool call at runtime
    rather than via a pre-seeded row.
    """
    # Revive cancelled/no-show rows on today so the count recovers toward 11
    conn.execute(
        "UPDATE appointments SET status = 'scheduled' "
        "WHERE doctor_id = 'dr-patel' AND date = ? "
        "AND status IN ('cancelled', 'no-show', 'no_show', 'completed')",
        (today_iso,),
    )
    # Trim to exactly 11 — if more than 11 scheduled, mark extras cancelled
    cur = conn.execute(
        "SELECT id FROM appointments WHERE doctor_id='dr-patel' AND date=? "
        "AND status='scheduled' ORDER BY time",
        (today_iso,),
    )
    ids = [row[0] for row in cur.fetchall()]
    if len(ids) > 11:
        extras = ids[11:]
        conn.executemany(
            "UPDATE appointments SET status='cancelled' WHERE id = ?",
            [(aid,) for aid in extras],
        )
    conn.commit()

    # Free up slots on the OTHER doctors today so the sick-day reschedule
    # can land all 11 patients with same-day alternatives. The randomised
    # appointment generator can saturate Chen/Kim, leaving fewer than 11
    # free slots; here we trim any "no-show" / "cancelled" wiggle rows and
    # push late-day non-critical appts off today onto tomorrow.
    cur = conn.execute(
        "SELECT id FROM appointments WHERE doctor_id IN ('dr-chen','dr-kim') "
        "AND date = ? AND status = 'scheduled' "
        "ORDER BY time DESC",
        (today_iso,),
    )
    other_ids = [row[0] for row in cur.fetchall()]
    # Target: leave at most 5 scheduled appts on Chen+Kim combined today
    overflow = other_ids[: max(0, len(other_ids) - 5)]
    if overflow:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        conn.executemany(
            "UPDATE appointments SET date = ? WHERE id = ?",
            [(tomorrow, aid) for aid in overflow],
        )
    conn.commit()
    conn.commit()


def load_doctor_unavailability():
    """Load pre-baked doctor_unavailability rows.

    Fixture rows use ``date_mode`` in {``today``, ``absolute``}:
      - ``today``: start_date = end_date = today (used for the demo sick-day)
      - ``absolute``: reads explicit start_date / end_date fields
    """
    fixture_path = FIXTURES_DIR / "doctor_unavailability.json"
    if not fixture_path.exists():
        print("No doctor_unavailability fixture found — skipping")
        return

    with open(fixture_path) as f:
        rows = json.load(f)

    today_iso = date.today().isoformat()
    conn = get_connection()
    # Wipe existing rows so reset produces a clean, seed-faithful state
    # (avoids stale entries created by earlier agent tool calls).
    conn.execute("DELETE FROM doctor_unavailability")
    conn.commit()

    _ensure_demo_affected_count(conn, rows, today_iso)

    for r in rows:
        mode = r.get("date_mode", "absolute")
        if mode == "today":
            start_d = end_d = today_iso
        else:
            start_d = r["start_date"]
            end_d = r.get("end_date", start_d)

        conn.execute(
            """INSERT INTO doctor_unavailability
               (doctor_id, start_date, end_date, start_time, end_time, reason, note, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                r["doctor_id"],
                start_d,
                end_d,
                r.get("start_time"),
                r.get("end_time"),
                r["reason"],
                r.get("note"),
                r.get("created_by", "user"),
            ),
        )
    conn.commit()
    conn.close()
    print(f"Loaded doctor_unavailability: {len(rows)} rows")


def load_patient_memories():
    """Load pre-baked patient memories into patient_memories table."""
    fixture_path = FIXTURES_DIR / "patient_memories.json"
    if not fixture_path.exists():
        print("No patient memories fixture found — skipping")
        return

    with open(fixture_path) as f:
        memories = json.load(f)

    now = datetime.now().isoformat()
    conn = get_connection()
    for m in memories:
        conn.execute(
            """INSERT OR REPLACE INTO patient_memories
               (id, patient_id, memory_type, content, source, confidence,
                first_observed, last_confirmed, observation_count, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m["id"],
                m["patient_id"],
                m["memory_type"],
                m["content"],
                m["source"],
                m["confidence"],
                m.get("first_observed", now),
                m.get("last_confirmed", now),
                m.get("observation_count", 1),
                m.get("status", "active"),
                m.get("metadata"),
            ),
        )
    conn.commit()
    conn.close()
    print(f"Loaded patient memories: {len(memories)} memories")


def load_insights_fixtures():
    """Load hand-crafted insights (patterns + unified skills) for the keynote demo.

    The unified model ships only the 2 seeded skills (Morning Briefing +
    Context-Aware Booking). Additional skills are generated live by the
    analysis pipeline (``/api/analysis/run``).
    """
    fixture_path = FIXTURES_DIR / "insights.json"
    if not fixture_path.exists():
        print("No insights fixture found — skipping")
        return

    with open(fixture_path) as f:
        data = json.load(f)

    now = datetime.now().isoformat()
    conn = get_connection()

    for p in data.get("patterns", []):
        conn.execute(
            """INSERT OR REPLACE INTO detected_patterns
               (id, detected_at, pattern_type, description, tool_sequence,
                occurrence_count, confidence, example_session_ids, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
            (p["id"], now, p["pattern_type"], p["description"],
             p["tool_sequence"], p["occurrence_count"], p["confidence"],
             p.get("example_session_ids")),
        )

    for sk in data.get("skills", []):
        conn.execute(
            """INSERT OR REPLACE INTO skills
               (id, pattern_id, name, description, trigger_description,
                agent_prompt_template, tool_config, batch_selection_hint,
                example_scenario, status, created_at, scheduled,
                schedule_cadence, schedule_time, schedule_day)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sk["id"], sk.get("pattern_id"), sk["name"], sk["description"],
             sk.get("trigger_description"), sk.get("agent_prompt_template"),
             sk.get("tool_config"), sk.get("batch_selection_hint"),
             sk.get("example_scenario"),
             sk.get("status", "pending_review"), now,
             1 if sk.get("scheduled") else 0,
             sk.get("schedule_cadence"), sk.get("schedule_time"),
             sk.get("schedule_day")),
        )

    conn.commit()
    conn.close()
    patterns = len(data.get("patterns", []))
    skills = len(data.get("skills", []))
    print(f"Loaded insights: {patterns} patterns, {skills} skills")


def load_conversation_fixtures():
    """Load pre-baked conversation fixtures into tool_call_log and conversation_log.

    Each conversation fixture file contains an array of sessions. Each session has:
    - session_id: unique session identifier
    - timestamp_base: ISO timestamp for the start of the session
    - turns: array of conversation turns

    Each turn has:
    - role: "user" or "assistant"
    - content: the message text
    - tool_calls (optional, assistant only): array of tool call records

    Timestamps increment by ~30 seconds per turn from timestamp_base.
    Tool calls within a turn are written to tool_call_log and their IDs
    are referenced in the conversation_log entry via tool_calls_in_turn.
    """
    convos_dir = FIXTURES_DIR / "conversations"
    if not convos_dir.exists():
        print("No conversation fixtures directory found — skipping")
        return

    fixture_files = sorted(convos_dir.glob("*.json"))
    if not fixture_files:
        print("No conversation fixture files found — skipping")
        return

    conn = get_connection()
    total_sessions = 0
    total_tool_calls = 0
    total_turns = 0

    for fixture_file in fixture_files:
        with open(fixture_file) as f:
            sessions = json.load(f)

        for session in sessions:
            session_id = session["session_id"]
            base_ts = datetime.fromisoformat(session["timestamp_base"])
            total_sessions += 1
            seq = 0
            tool_seq = 0

            for turn in session["turns"]:
                seq += 1
                # Increment timestamp ~30 seconds per turn from base
                turn_ts = base_ts + timedelta(seconds=30 * (seq - 1))
                turn_ts_str = turn_ts.isoformat()
                tool_call_ids = []

                # Log tool calls if present
                if turn.get("tool_calls"):
                    for tc in turn["tool_calls"]:
                        tool_seq += 1
                        total_tool_calls += 1
                        tc_id = f"tc-{session_id}-{tool_seq}"
                        tool_call_ids.append(tc_id)
                        conn.execute(
                            "INSERT INTO tool_call_log (session_id, timestamp, tool_name, tool_params, result_summary, duration_ms, sequence_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                session_id,
                                turn_ts_str,
                                tc["tool"],
                                json.dumps(tc.get("params", {})),
                                json.dumps(tc.get("result", {})),
                                tc.get("duration_ms", 50),
                                tool_seq,
                            ),
                        )

                conn.execute(
                    "INSERT INTO conversation_log (session_id, timestamp, role, content, tool_calls_in_turn, sequence_number) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        turn_ts_str,
                        turn["role"],
                        turn["content"],
                        json.dumps(tool_call_ids) if tool_call_ids else None,
                        seq,
                    ),
                )
                total_turns += 1

    conn.commit()
    conn.close()
    print(f"Loaded conversations: {total_sessions} sessions, {total_tool_calls} tool calls, {total_turns} conversation turns")


def load_ui_activity_fixtures():
    """Load pre-baked UI activity data into ui_activity_log.

    Each entry has: session_id, timestamp, action_type, action_detail (JSON),
    entity_type, entity_id, view, duration_ms, metadata (JSON).
    """
    fixture_path = FIXTURES_DIR / "ui_activities.json"
    if not fixture_path.exists():
        print("No UI activity fixtures found — skipping")
        return

    with open(fixture_path) as f:
        activities = json.load(f)

    conn = get_connection()
    for a in activities:
        conn.execute(
            """INSERT INTO ui_activity_log
               (session_id, timestamp, action_type, action_detail, entity_type, entity_id, view, duration_ms, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                a["session_id"],
                a["timestamp"],
                a["action_type"],
                a.get("action_detail"),
                a.get("entity_type"),
                a.get("entity_id"),
                a.get("view"),
                a.get("duration_ms"),
                a.get("metadata"),
            ),
        )

    conn.commit()
    conn.close()
    print(f"Loaded UI activities: {len(activities)} events")


def reset_db():
    """Drop all tables and re-seed the database from scratch.

    This is useful during development and demo resets to return to a
    known-good starting state.
    """
    conn = get_connection()
    # Disable FK checks while dropping to avoid ordering issues
    conn.execute("PRAGMA foreign_keys = OFF")

    # Fetch all table names from the database
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    for (table_name,) in tables:
        conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")  # nosec B608  # nosemgrep

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    print("All tables dropped. Re-initialising and seeding...")
    seed_all()
    load_patient_memories()
    load_insights_fixtures()
    load_conversation_fixtures()
    load_ui_activity_fixtures()
    load_doctor_unavailability()
    print("Database reset complete.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_db()
    else:
        seed_all()
        load_patient_memories()
        load_insights_fixtures()
        load_conversation_fixtures()
        load_ui_activity_fixtures()
        load_doctor_unavailability()

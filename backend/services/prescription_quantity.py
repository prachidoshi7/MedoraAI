"""Conservative dispense-quantity suggestions for pharmacy billing.

This helper does not make or alter a prescription. It translates common
clinician-entered frequency and duration phrases into an editable cart default.
Unclear directions deliberately fall back to one unit for pharmacist review.
"""

from __future__ import annotations

import math
import re


_NUMBER_WORDS = {
    "one": 1.0,
    "once": 1.0,
    "two": 2.0,
    "twice": 2.0,
    "three": 3.0,
    "thrice": 3.0,
    "four": 4.0,
}


def _number(value: str) -> float | None:
    value = value.strip().lower()
    if value in _NUMBER_WORDS:
        return _NUMBER_WORDS[value]
    try:
        return float(value)
    except ValueError:
        return None


def _duration_days(text: str) -> int | None:
    normalized = " ".join(text.lower().replace("-", " ").split())
    match = re.search(
        r"\b(\d+(?:\.\d+)?|one|two|three|four)\s*"
        r"(day|days|week|weeks|month|months|year|years)\b",
        normalized,
    )
    if not match:
        return None
    amount = _number(match.group(1))
    if amount is None or amount <= 0:
        return None
    multiplier = {
        "day": 1,
        "days": 1,
        "week": 7,
        "weeks": 7,
        "month": 30,
        "months": 30,
        "year": 365,
        "years": 365,
    }[match.group(2)]
    return max(1, math.ceil(amount * multiplier))


def _daily_frequency(text: str) -> float | None:
    normalized = " ".join(text.lower().replace("-", " ").split())
    if not normalized:
        return None
    if re.search(r"\b(prn|sos|as needed|when required)\b", normalized):
        return None

    every_hours = re.search(r"\bevery\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", normalized)
    if every_hours:
        interval = float(every_hours.group(1))
        return 24.0 / interval if interval > 0 else None

    explicit = re.search(
        r"\b(\d+(?:\.\d+)?|one|once|two|twice|three|thrice|four)\s*"
        r"(?:times?|doses?)\s*(?:(?:a|per)\s*)?(?:day|daily)\b",
        normalized,
    )
    if explicit:
        return _number(explicit.group(1))

    weekly = re.search(
        r"\b(\d+(?:\.\d+)?|one|once|two|twice|three|thrice|four)\s*"
        r"(?:times?|doses?)\s*(?:(?:a|per)\s*)?week\b",
        normalized,
    )
    if weekly:
        amount = _number(weekly.group(1))
        return amount / 7.0 if amount is not None else None

    patterns = (
        (r"\b(qid|four times daily|four times a day)\b", 4.0),
        (r"\b(tid|tds|three times daily|three times a day|thrice daily)\b", 3.0),
        (r"\b(bid|bd|twice daily|twice a day)\b", 2.0),
        (r"\b(qd|od|once daily|once a day|daily|at night|nightly)\b", 1.0),
        (r"\b(alternate days?|every other day)\b", 0.5),
    )
    for pattern, value in patterns:
        if re.search(pattern, normalized):
            return value

    # Doctors sometimes place "2 doses" in the frequency field without
    # adding "daily". Treat that common shorthand as doses per day.
    short_dose = re.search(
        r"\b(\d+(?:\.\d+)?|one|once|two|twice|three|thrice|four)\s*doses?\b",
        normalized,
    )
    return _number(short_dose.group(1)) if short_dose else None


def _units_per_administration(dosage: str) -> float:
    normalized = " ".join(dosage.lower().replace("-", " ").split())
    match = re.search(
        r"\b(\d+(?:\.\d+)?|one|two|three|four)\s*"
        r"(?:tablets?|tabs?|capsules?|caps?|pills?)\b",
        normalized,
    )
    amount = _number(match.group(1)) if match else None
    return amount if amount is not None and amount > 0 else 1.0


def suggest_dispense_quantity(medication: dict) -> tuple[int, str]:
    """Return an editable unit suggestion and a short explanation."""

    dosage = str(medication.get("dosage") or "")
    frequency_text = str(medication.get("frequency") or "")
    duration_text = str(medication.get("duration") or "")
    combined_directions = " ".join((dosage, frequency_text, duration_text))
    days = _duration_days(duration_text) or _duration_days(combined_directions)
    frequency = _daily_frequency(frequency_text)

    # Support the requested shorthand: dosage/frequency entered as "2 doses"
    # with a duration such as "1 month" suggests 2 × 30 = 60 units.
    if frequency is None:
        frequency = _daily_frequency(dosage)
    units = _units_per_administration(dosage)

    if days is None:
        return 1, "Duration unclear — pharmacist review required"
    if frequency is None:
        frequency = 1.0
        frequency_label = "1 administration/day assumed"
    else:
        frequency_label = f"{frequency:g} administration(s)/day"

    quantity = max(1, min(1000, math.ceil(days * frequency * units)))
    unit_label = f" × {units:g} unit(s)" if units != 1 else ""
    return quantity, f"{frequency_label} × {days} day(s){unit_label}"

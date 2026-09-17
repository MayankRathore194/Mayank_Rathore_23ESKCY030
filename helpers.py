"""
helpers.py
----------
Small shared utilities used across route files, so logic like
"is this batch expired?" lives in exactly one place.
"""

from datetime import datetime, date


def parse_date(date_str):
    """Turn a 'YYYY-MM-DD' string (from an HTML <input type=date>) into
    a datetime at midnight, so it can be stored/compared consistently
    in MongoDB (which stores dates as datetimes, not plain dates)."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def today_start():
    """Today at midnight, as a datetime — matches how expiry_date is stored."""
    return datetime.combine(date.today(), datetime.min.time())


def is_expired(expiry_date, as_of=None):
    """A batch is expired once its expiry date has passed.
    We treat the expiry date itself as still valid (expires END of that day)."""
    as_of = as_of or today_start()
    return expiry_date < as_of


def batch_status(expiry_date, as_of=None):
    return "Expired" if is_expired(expiry_date, as_of) else "Valid"


def sellable_match(extra=None):
    """MongoDB filter for in-date, non-quarantined stock with quantity > 0."""
    match = {
        "expiry_date": {"$gte": today_start()},
        "quantity": {"$gt": 0},
        "quarantined": {"$ne": True},
    }
    if extra:
        match.update(extra)
    return match


def serialize_batch(doc):
    """Convert a MongoDB batch document into a plain dict safe for
    templates / JSON (stringify the ObjectId, format the date)."""
    return {
        "id": str(doc["_id"]),
        "medicine_name": doc["medicine_name"],
        "batch_number": doc["batch_number"],
        "quantity": doc["quantity"],
        "expiry_date": doc["expiry_date"].strftime("%Y-%m-%d"),
        "status": batch_status(doc["expiry_date"]),
        "quarantined": doc.get("quarantined", False),
        "expiring_flagged": doc.get("expiring_flagged", False),
    }

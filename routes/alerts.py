"""
routes/alerts.py
-----------------
Flags batches that are still in-date but expiring soon, so the
pharmacist can prioritize selling/rotating them (or return/dispose
once they do expire).
"""

from datetime import timedelta
from flask import Blueprint, render_template
from config import batches, EXPIRY_ALERT_DAYS
from helpers import today_start, serialize_batch

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/alerts")
def alerts():
    start = today_start()
    cutoff = start + timedelta(days=EXPIRY_ALERT_DAYS)

    docs = batches.find(
        {
            "expiry_date": {"$gte": start, "$lte": cutoff},
            "quantity": {"$gt": 0},
        }
    ).sort("expiry_date", 1)

    rows = [serialize_batch(d) for d in docs]
    return render_template("alerts.html", rows=rows, window_days=EXPIRY_ALERT_DAYS)

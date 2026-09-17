"""
routes/maintenance.py
----------------------
Daily maintenance tasks: flag expiring batches and quarantine expired ones.
Exposed via POST /clock which returns a small report.
"""
from datetime import timedelta
from flask import Blueprint, jsonify
from config import batches, DAILY_QUARANTINE_DAYS
from helpers import today_start
from routes.notifications import scan_reorder_alerts_for_medicines

maintenance_bp = Blueprint("maintenance", __name__)


@maintenance_bp.route("/clock", methods=["POST"])
def clock():
    """Run a maintenance tick:
    - flag batches expiring within DAILY_QUARANTINE_DAYS
    - mark expired batches as quarantined
    - send re-order alerts for medicines now below threshold
    Returns a JSON report with counts.
    """
    start = today_start()
    cutoff = start + timedelta(days=DAILY_QUARANTINE_DAYS)

    flag_filter = {
        "expiry_date": {"$gte": start, "$lte": cutoff},
        "quantity": {"$gt": 0},
        "expiring_flagged": {"$ne": True},
    }
    flag_update = {"$set": {"expiring_flagged": True, "flagged_at": start}}
    flag_result = batches.update_many(flag_filter, flag_update)

    quarantine_filter = {"expiry_date": {"$lt": start}, "quarantined": {"$ne": True}}
    quarantine_update = {"$set": {"quarantined": True, "quarantined_at": start}}
    quarantine_result = batches.update_many(quarantine_filter, quarantine_update)

    affected_meds = batches.distinct(
        "medicine_name", {"quarantined_at": start}
    )
    reorder_alerts_sent = scan_reorder_alerts_for_medicines(affected_meds)

    report = {
        "flagged_count": flag_result.modified_count,
        "quarantined_count": quarantine_result.modified_count,
        "reorder_alerts_sent": reorder_alerts_sent,
    }

    return jsonify(report)

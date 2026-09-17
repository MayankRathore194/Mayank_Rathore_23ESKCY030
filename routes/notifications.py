"""
routes/notifications.py
------------------------
Notification helpers and a simple /outbox endpoint for testing.
"""
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
from config import outbox, batches, REORDER_THRESHOLD
from helpers import sellable_match

notifications_bp = Blueprint("notifications", __name__)


def send_reorder_alert(medicine_name, current_qty, threshold=None):
    threshold = threshold or REORDER_THRESHOLD
    msg = {
        "medicine_name": medicine_name,
        "current_quantity": current_qty,
        "threshold": threshold,
        "message": f"Re-order needed for {medicine_name}: {current_qty} <= {threshold}",
        "timestamp": datetime.utcnow(),
    }
    outbox.insert_one(msg)
    return msg


def get_sellable_stock(medicine_name):
    pipeline = [
        {"$match": sellable_match({"medicine_name": medicine_name})},
        {"$group": {"_id": "$medicine_name", "total": {"$sum": "$quantity"}}},
    ]
    agg = list(batches.aggregate(pipeline))
    return agg[0]["total"] if agg else 0


def check_and_notify_if_needed(medicine_name, threshold=None):
    qty = get_sellable_stock(medicine_name)
    threshold = threshold or REORDER_THRESHOLD
    if qty <= threshold:
        return send_reorder_alert(medicine_name, qty, threshold)
    return None


def scan_reorder_alerts_for_medicines(medicine_names, threshold=None):
    """Check reorder threshold for each medicine; return alert count."""
    sent = 0
    for name in medicine_names:
        if check_and_notify_if_needed(name, threshold):
            sent += 1
    return sent


@notifications_bp.route("/outbox")
def outbox_list():
    docs = list(outbox.find().sort("timestamp", -1).limit(100))
    for d in docs:
        d["timestamp"] = d["timestamp"].isoformat()
        d["_id"] = str(d["_id"])
    if request.accept_mimetypes.best == "text/html":
        return render_template("outbox.html", messages=docs)
    return jsonify(docs)

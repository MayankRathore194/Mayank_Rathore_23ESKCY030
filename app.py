"""
app.py
------
Entry point. Starts Flask, registers each feature's routes (blueprints),
and provides the dashboard homepage with a quick overview.

Run with:
    python app.py
Then visit:
    http://127.0.0.1:5000
"""

from flask import Flask, render_template
from datetime import timedelta

from config import batches, EXPIRY_ALERT_DAYS
from helpers import today_start

from routes.inventory import inventory_bp
from routes.dispensing import dispensing_bp
from routes.search import search_bp
from routes.alerts import alerts_bp
from routes.maintenance import maintenance_bp
from routes.importer import importer_bp
from routes.notifications import notifications_bp

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this"  # needed for flash() messages

app.register_blueprint(inventory_bp)
app.register_blueprint(dispensing_bp)
app.register_blueprint(search_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(maintenance_bp)
app.register_blueprint(importer_bp)
app.register_blueprint(notifications_bp)


@app.route("/")
def dashboard():
    start = today_start()
    cutoff = start + timedelta(days=EXPIRY_ALERT_DAYS)

    total_batches = batches.count_documents({})
    expired_batches = batches.count_documents({"expiry_date": {"$lt": start}})
    expiring_soon = batches.count_documents(
        {
            "expiry_date": {"$gte": start, "$lte": cutoff},
            "quantity": {"$gt": 0},
        }
    )

    sellable_agg = list(
        batches.aggregate(
            [
                {"$match": {"expiry_date": {"$gte": start}}},
                {"$group": {"_id": None, "total": {"$sum": "$quantity"}}},
            ]
        )
    )
    sellable_stock = sellable_agg[0]["total"] if sellable_agg else 0

    distinct_medicines = len(batches.distinct("medicine_name"))

    stats = {
        "total_medicines": distinct_medicines,
        "total_batches": total_batches,
        "sellable_stock": sellable_stock,
        "expiring_soon": expiring_soon,
        "expired_batches": expired_batches,
    }
    return render_template("dashboard.html", stats=stats)


if __name__ == "__main__":
    app.run(debug=True)

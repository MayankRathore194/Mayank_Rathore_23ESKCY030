"""
routes/search.py
-----------------
Answers "do we have X in date?" — sums quantity across all
non-expired batches for a medicine.
"""

from flask import Blueprint, render_template, request
from config import batches
from helpers import sellable_match

search_bp = Blueprint("search", __name__)


@search_bp.route("/search", methods=["GET"])
def search():
    medicine_name = request.args.get("medicine_name", "").strip()
    result = None

    if medicine_name:
        pipeline = [
            {"$match": sellable_match({"medicine_name": medicine_name})},
            {"$group": {"_id": "$medicine_name", "total": {"$sum": "$quantity"}}},
        ]
        agg = list(batches.aggregate(pipeline))
        sellable_stock = agg[0]["total"] if agg else 0

        result = {
            "medicine_name": medicine_name,
            "sellable_stock": sellable_stock,
            "available": sellable_stock > 0,
        }

    return render_template("search.html", result=result, query=medicine_name)

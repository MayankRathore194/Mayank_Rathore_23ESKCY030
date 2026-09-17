"""
routes/importer.py
-------------------
Import messy CSV batch lists and normalize them into the `batches` collection.
Accepts a text CSV in the `csv_data` form field (or file upload named `file`).
Returns a JSON report with imported, deduped, and rejected entries.
"""
import csv
import re
from io import StringIO
from datetime import datetime
from flask import Blueprint, request, render_template, jsonify
from config import batches
from helpers import parse_date
from routes.notifications import check_and_notify_if_needed

importer_bp = Blueprint("importer", __name__)


def parse_quantity(qraw):
    if qraw is None:
        return None
    s = str(qraw).strip()
    # extract integer from strings like '10 units' or ' 5 '
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def parse_maybe_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            # normalize to midnight
            return datetime.combine(dt.date(), datetime.min.time())
        except Exception:
            continue
    return None


@importer_bp.route("/import", methods=["GET", "POST"])
def do_import():
    if request.method == "GET":
        return render_template("import.html")

    # read CSV from textarea or uploaded file
    data = ""
    if "csv_data" in request.form and request.form.get("csv_data").strip():
        data = request.form.get("csv_data")
    elif "file" in request.files:
        f = request.files["file"]
        data = f.read().decode("utf-8")

    if not data:
        return jsonify({"error": "No CSV data provided."}), 400

    reader = csv.DictReader(StringIO(data))
    buffer = {}
    rejected = []

    for i, row in enumerate(reader, start=1):
        med = (row.get("medicine_name") or "").strip()
        batch = (row.get("batch_number") or "").strip()
        qty = parse_quantity(row.get("quantity"))
        expiry = parse_maybe_date(row.get("expiry_date"))

        if not med or not batch or qty is None or expiry is None:
            rejected.append({"row": i, "raw": row})
            continue

        key = (med, batch)
        if key not in buffer:
            buffer[key] = {"medicine_name": med, "batch_number": batch, "quantity": 0, "expiry_date": expiry}
        # sum quantities when duplicates found in input
        buffer[key]["quantity"] += qty
        # pick the latest expiry if different
        if expiry > buffer[key]["expiry_date"]:
            buffer[key]["expiry_date"] = expiry

    imported = []
    deduped = []

    for (med, batch), doc in buffer.items():
        existing = batches.find_one({"medicine_name": med, "batch_number": batch})
        if existing:
            # treat as deduped: add quantity and update expiry to later date
            new_qty = existing.get("quantity", 0) + doc["quantity"]
            batches.update_one({"_id": existing["_id"]}, {"$set": {"quantity": new_qty, "expiry_date": doc["expiry_date"]}})
            deduped.append({"medicine_name": med, "batch_number": batch, "added": doc["quantity"], "new_quantity": new_qty})
        else:
            to_insert = {"medicine_name": med, "batch_number": batch, "quantity": doc["quantity"], "expiry_date": doc["expiry_date"]}
            batches.insert_one(to_insert)
            imported.append(to_insert)

        # after changing stock, check reorder threshold for this medicine
        check_and_notify_if_needed(med)

    report = {
        "imported": len(imported),
        "deduped": len(deduped),
        "rejected": len(rejected),
        "imported_items": [
            {**item, "expiry_date": item["expiry_date"].strftime("%Y-%m-%d")}
            for item in imported[:10]
        ],
        "deduped_items": deduped[:10],
        "rejected_items": rejected[:10],
    }
    if request.accept_mimetypes.best == "text/html":
        return render_template("import.html", report=report)
    return jsonify(report)

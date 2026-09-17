"""
routes/inventory.py
--------------------
Adding new medicine batches, and viewing the full inventory list.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from config import batches
from helpers import parse_date, serialize_batch
from routes.notifications import check_and_notify_if_needed

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/inventory/add", methods=["GET", "POST"])
def add_batch():
    if request.method == "POST":
        medicine_name = request.form.get("medicine_name", "").strip()
        batch_number = request.form.get("batch_number", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        expiry_raw = request.form.get("expiry_date", "").strip()

        # --- basic validation ---
        errors = []
        if not medicine_name:
            errors.append("Medicine name is required.")
        if not batch_number:
            errors.append("Batch number is required.")

        quantity = None
        if not quantity_raw:
            errors.append("Quantity is required.")
        else:
            try:
                quantity = int(quantity_raw)
                if quantity < 0:
                    errors.append("Quantity cannot be negative.")
            except ValueError:
                errors.append("Quantity must be a whole number.")

        expiry_date = None
        if not expiry_raw:
            errors.append("Expiry date is required.")
        else:
            try:
                expiry_date = parse_date(expiry_raw)
            except ValueError:
                errors.append("Expiry date must be a valid date.")

        # A given medicine + batch number should be unique
        if not errors and batches.find_one(
            {"medicine_name": medicine_name, "batch_number": batch_number}
        ):
            errors.append(
                f"Batch '{batch_number}' already exists for {medicine_name}."
            )

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("add_batch.html", form=request.form)

        batches.insert_one(
            {
                "medicine_name": medicine_name,
                "batch_number": batch_number,
                "quantity": quantity,
                "expiry_date": expiry_date,
            }
        )
        check_and_notify_if_needed(medicine_name)
        flash(f"Batch {batch_number} for {medicine_name} added.", "success")
        return redirect(url_for("inventory.view_inventory"))

    return render_template("add_batch.html", form={})


@inventory_bp.route("/inventory")
def view_inventory():
    docs = batches.find().sort(
        [("medicine_name", 1), ("expiry_date", 1)]
    )
    rows = [serialize_batch(d) for d in docs]
    return render_template("inventory.html", rows=rows)

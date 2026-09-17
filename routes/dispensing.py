"""
routes/dispensing.py
---------------------
The most important file in the project: First-Expiry-First-Out (FEFO)
dispensing.

Rules enforced here:
  1. Expired batches are never touched.
  2. Among valid batches, the one expiring soonest is used first.
  3. Dispensing can span multiple batches (partial dispensing).
  4. Stock is only deducted in the database once we've confirmed
     there's enough in-date stock to fulfill the whole request —
     otherwise nothing is deducted (no partial, silently-wrong dispenses).
"""

from flask import Blueprint, render_template, request, flash
from config import batches
from helpers import sellable_match
from routes.notifications import check_and_notify_if_needed

dispensing_bp = Blueprint("dispensing", __name__)


def get_fefo_plan(medicine_name, quantity_needed):
    """
    Work out which batches to dispense from, and how much from each,
    following FEFO. Does NOT write to the database.

    Returns a dict:
      {
        "plan": [{"batch_number": ..., "take": ..., "expiry_date": ...}, ...],
        "available": <int, total in-date stock found>,
        "fulfilled": <bool, was quantity_needed fully covered?>
      }
    """
    valid_batches = list(
        batches.find(sellable_match({"medicine_name": medicine_name})).sort(
            "expiry_date", 1
        )  # soonest-expiring first = FEFO order
    )

    plan = []
    remaining = quantity_needed
    total_available = 0

    for b in valid_batches:
        total_available += b["quantity"]
        if remaining <= 0:
            continue
        take = min(b["quantity"], remaining)
        if take > 0:
            plan.append(
                {
                    "_id": b["_id"],
                    "batch_number": b["batch_number"],
                    "take": take,
                    "expiry_date": b["expiry_date"].strftime("%Y-%m-%d"),
                }
            )
            remaining -= take

    return {
        "plan": plan,
        "available": total_available,
        "fulfilled": remaining <= 0,
    }


@dispensing_bp.route("/dispense", methods=["GET", "POST"])
def dispense():
    result = None

    if request.method == "POST":
        medicine_name = request.form.get("medicine_name", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()

        quantity_needed = None
        if not medicine_name:
            flash("Medicine name is required.", "error")
        elif not quantity_raw or not quantity_raw.isdigit() or int(quantity_raw) <= 0:
            flash("Enter a valid positive quantity.", "error")
        else:
            quantity_needed = int(quantity_raw)

        if medicine_name and quantity_needed:
            fefo = get_fefo_plan(medicine_name, quantity_needed)

            if not fefo["plan"] and fefo["available"] == 0:
                flash(f"No in-date stock found for {medicine_name}.", "error")
            elif not fefo["fulfilled"]:
                flash(
                    f"Not enough in-date stock. Requested {quantity_needed}, "
                    f"only {fefo['available']} available (in-date).",
                    "error",
                )
            else:
                # Enough stock exists — commit the deductions now.
                for step in fefo["plan"]:
                    batches.update_one(
                        {"_id": step["_id"]}, {"$inc": {"quantity": -step["take"]}}
                    )
                # After committing, check if remaining in-date stock is below threshold
                check_and_notify_if_needed(medicine_name)
                result = {
                    "medicine_name": medicine_name,
                    "quantity_needed": quantity_needed,
                    "plan": fefo["plan"],
                }
                flash(
                    f"Dispensed {quantity_needed} units of {medicine_name}.",
                    "success",
                )

    return render_template("dispense.html", result=result)

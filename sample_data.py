"""
sample_data.py
----------------
Insert example batches into the configured MongoDB for manual testing.

Usage:
  Set MONGODB_URI in .env then run:
    python sample_data.py
"""
from datetime import datetime, timedelta
from config import batches

def make_date(days_from_today):
    return datetime.combine((datetime.today() + timedelta(days=days_from_today)).date(), datetime.min.time())

EXAMPLES = [
    # medicine, batch, qty, days until expiry
    ("Paracetamol", "P-001", 50, 60),
    ("Paracetamol", "P-002", 30, 10),
    ("Ibuprofen", "I-001", 20, 5),
    ("Ibuprofen", "I-002", 0, 90),
    ("Aspirin", "A-001", 100, -5),  # expired
]

def load():
    print("Inserting sample batches...")
    for med, batch, qty, days in EXAMPLES:
        doc = {
            "medicine_name": med,
            "batch_number": batch,
            "quantity": qty,
            "expiry_date": make_date(days),
        }
        existing = batches.find_one({"medicine_name": med, "batch_number": batch})
        if existing:
            print(f"Updating existing {med} {batch}")
            batches.update_one({"_id": existing["_id"]}, {"$set": doc})
        else:
            batches.insert_one(doc)
            print(f"Inserted {med} {batch}")

    print("Done.")

if __name__ == "__main__":
    load()

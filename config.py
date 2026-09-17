"""
config.py
---------
Central place for configuration and the MongoDB Atlas connection.

The connection string is read from the environment (via a .env file),
never hardcoded here. This means:
  1. Your real username/password never sits in a source file.
  2. You can safely share this code without leaking credentials.
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

# Load variables from a local .env file (if present) into the environment
load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB = os.environ.get("MONGODB_DB", "pharmacy_inventory")
EXPIRY_ALERT_DAYS = int(os.environ.get("EXPIRY_ALERT_DAYS", "30"))
# Number of days for the daily quarantine job to flag upcoming expiries
DAILY_QUARANTINE_DAYS = int(os.environ.get("DAILY_QUARANTINE_DAYS", "7"))

# Threshold for re-order alerts (per medicine default)
REORDER_THRESHOLD = int(os.environ.get("REORDER_THRESHOLD", "10"))

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is not set. Copy .env.example to .env and fill in "
        "your MongoDB Atlas connection string."
    )

# A single shared client for the whole app
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

# The one collection this project needs
batches = db["batches"]
outbox = db["outbox"]

# Helpful indexes:
# - medicine_name: every search/dispense/alert query filters on this
# - expiry_date: FEFO sorting and alert queries sort/filter on this
batches.create_index([("medicine_name", ASCENDING)])
batches.create_index([("expiry_date", ASCENDING)])

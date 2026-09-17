# Pharmacy Inventory (FEFO)

Flask app for batch-based pharmacy inventory with FEFO dispensing, expiry alerts, and three graded "twist" features.

## Quick start

1. Copy `.env.example` to `.env` and set `MONGODB_URI` (and optional settings).

2. Install dependencies:

```
pip install -r requirements.txt
```

3. (Optional) Load sample data:

```
python sample_data.py
```

4. Run the app:

```
python app.py
```

Open http://127.0.0.1:5000

## Twist features

### Level 1 — Daily maintenance (`POST /clock`)

Flags batches expiring within 7 days and quarantines expired ones. Returns counts:

```json
{ "flagged_count": 2, "quarantined_count": 1, "reorder_alerts_sent": 0 }
```

```bash
curl -X POST http://127.0.0.1:5000/clock
```

### Level 2 — Messy CSV import (`POST /import`)

Import CSV with nulls, quantities like `10 units`, mixed date formats, and duplicate rows. Returns:

```json
{ "imported": 3, "deduped": 1, "rejected": 2 }
```

Browser UI: http://127.0.0.1:5000/import

### Level 3 — Re-order alerts (`GET /outbox`)

When in-date stock for a medicine drops to `REORDER_THRESHOLD` (default 10) after dispense, import, or clock quarantine, an alert is written to the outbox.

```bash
curl http://127.0.0.1:5000/outbox
```

Browser UI: http://127.0.0.1:5000/outbox

## Tests

```
pytest -q
```

## Core features

- FEFO dispensing (`routes/dispensing.py`)
- Sellable stock search (excludes expired and quarantined batches)
- Expiry alerts page (`EXPIRY_ALERT_DAYS`, default 30)

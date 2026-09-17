# Pharmacy Inventory (FEFO)

Flask web application for batch-based pharmacy inventory management with **First-Expiry-First-Out (FEFO)** dispensing, expiry alerts, daily maintenance, messy CSV import, and re-order notifications.

## Features

- **Inventory management**: Add and view medicine batches (medicine name, batch number, quantity, expiry date).
- **FEFO dispensing**: Always dispenses from the soonest-expiring in-date, non-quarantined batch first. Supports multi-batch fulfilment; refuses partial dispenses if stock is insufficient.
- **Sellable stock search**: Returns only in-date, non-quarantined quantity > 0.
- **Expiry alerts**: Lists batches expiring within a configurable window (default 30 days).
- **Level 1 – Daily maintenance** (`POST /clock`): Flags batches expiring within 7 days and quarantines already-expired ones; triggers re-order alerts for affected medicines.
- **Level 2 – Messy CSV import** (`POST /import`): Accepts imperfect CSVs (nulls, “10 units”, mixed date formats `YYYY-MM-DD` / `dd/mm/yyyy` / `dd-mm-yyyy`, duplicate rows). Deduplicates by medicine+batch, sums quantities, keeps latest expiry.
- **Level 3 – Re-order alerts** (`GET /outbox`): When in-date sellable stock for a medicine falls to or below `REORDER_THRESHOLD` (default 10), an alert is written to the outbox collection.

## Project layout

```
.
├── app.py                 # Flask entry point + dashboard
├── config.py              # MongoDB connection, env vars, indexes
├── helpers.py             # Shared date/status/sellable helpers
├── sample_data.py         # Optional sample batches
├── requirements.txt
├── .env.example
├── routes/                # (or flat .py files imported as routes.*)
│   ├── inventory.py
│   ├── dispensing.py
│   ├── search.py
│   ├── alerts.py
│   ├── maintenance.py
│   ├── importer.py
│   └── notifications.py
├── templates/             # Jinja2 HTML (or flat .html files)
├── static/style.css
└── tests/
    ├── test_dispense.py
    ├── test_importer.py
    ├── test_maintenance.py
    ├── test_notifications.py
    └── test_search.py
```

> **Note on structure**: The supplied source may place route modules and templates in the project root. Create a `routes/` package (with `__init__.py`) and a `templates/` + `static/` layout, or adjust the imports / `Flask` template/static folders accordingly before running.

## Prerequisites

- Python 3.10+
- A MongoDB Atlas cluster (or local MongoDB) and a connection string
- `pip`

## Setup

1. Clone / copy the project and enter the directory.

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.rawu8tm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGODB_DB=pharmacy_inventory
```

Optional settings (defaults shown):

```
EXPIRY_ALERT_DAYS=30
DAILY_QUARANTINE_DAYS=7
REORDER_THRESHOLD=10
```

5. (Optional) Load sample data:

```bash
python sample_data.py
```

## Running the application

```bash
python app.py
```

Open **http://127.0.0.1:5000** in a browser.

The app runs in debug mode by default (`app.run(debug=True)`).

## Debugging

- **Connection errors**: Confirm `MONGODB_URI` is correct and the Atlas IP allow-list includes your current IP (or `0.0.0.0/0` for testing). Check that the database user has read/write rights.
- **Import errors (`ModuleNotFoundError: routes`)**: Ensure a `routes/` directory exists containing the blueprint modules and an empty `__init__.py`, *or* change the imports in `app.py` to match the flat layout.
- **Template / static 404**: Place HTML files under `templates/` and `style.css` under `static/`, or configure `Flask(..., template_folder=..., static_folder=...)`.
- **Date / timezone surprises**: All expiry comparisons use midnight local date via `helpers.today_start()`. MongoDB stores datetimes; the helpers normalise consistently.
- **Tests failing because of real MongoDB**: Tests use `mongomock`. Run them with:

```bash
pytest -q
```

- **Flash messages not appearing**: `app.secret_key` must be set (already present in `app.py`).
- **Re-order alerts not firing**: Check that sellable stock (in-date + not quarantined) really is ≤ `REORDER_THRESHOLD` after a dispense / import / quarantine. Inspect the outbox via `GET /outbox` or the UI.

Useful debug commands:

```bash
# Force a maintenance tick
curl -X POST http://127.0.0.1:5000/clock

# View re-order outbox (JSON)
curl -H "Accept: application/json" http://127.0.0.1:5000/outbox

# Run only one test file
pytest tests/test_dispense.py -v
```

## API / HTTP endpoints

| Method | Path              | Description |
|--------|-------------------|-------------|
| GET    | `/`               | Dashboard with aggregate stats |
| GET    | `/inventory`      | Full inventory table |
| GET/POST | `/inventory/add` | Form to add a new batch |
| GET/POST | `/dispense`     | FEFO dispensing form + result |
| GET    | `/search`         | Search sellable stock by medicine name (`?medicine_name=...`) |
| GET    | `/alerts`         | Batches expiring within `EXPIRY_ALERT_DAYS` |
| GET/POST | `/import`       | CSV import UI + processing (accepts `csv_data` or file upload) |
| POST   | `/clock`          | Daily maintenance: flag + quarantine + reorder scan |
| GET    | `/outbox`         | Re-order alert messages (HTML or JSON depending on `Accept`) |

### Example requests

```bash
# Maintenance tick
curl -X POST http://127.0.0.1:5000/clock
# → {"flagged_count": 2, "quarantined_count": 1, "reorder_alerts_sent": 0}

# CSV import (JSON response)
curl -X POST http://127.0.0.1:5000/import \
  -H "Accept: application/json" \
  -d 'csv_data=medicine_name,batch_number,quantity,expiry_date%0AParacetamol,B001,10 units,2026-12-31'

# Outbox
curl -H "Accept: application/json" http://127.0.0.1:5000/outbox
```

## Tests

```bash
pytest -q
```

Tests cover:

- FEFO plan ordering and partial-stock refusal
- Messy CSV parsing, deduplication and rejection counts
- Clock flagging / quarantine idempotency
- Re-order threshold logic (including quarantined stock exclusion)
- Sellable-stock search ignoring expired batches

All tests use in-memory `mongomock` collections; no real MongoDB is required.

## Configuration reference

| Variable              | Default | Purpose |
|-----------------------|---------|---------|
| `MONGODB_URI`         | (required) | Atlas / MongoDB connection string |
| `MONGODB_DB`          | `pharmacy_inventory` | Database name |
| `EXPIRY_ALERT_DAYS`   | `30`    | Window shown on Alerts page |
| `DAILY_QUARANTINE_DAYS` | `7`   | Window used by `/clock` to flag “expiring soon” |
| `REORDER_THRESHOLD`   | `10`    | Per-medicine sellable-stock threshold for outbox alerts |

## Licence / notes

Developed as a teaching / assessment project demonstrating FEFO inventory, defensive CSV import, and simple event-driven notifications. Credentials must never be committed; keep `.env` out of version control (already listed in `.gitignore`).

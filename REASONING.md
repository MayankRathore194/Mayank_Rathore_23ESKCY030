# REASONING.md — Thought process, design decisions, testing & fixes

## 1. Problem understanding

The core requirement is a pharmacy inventory system that respects **FEFO** (First-Expiry-First-Out). Key constraints:

- Never dispense from an expired batch.
- Prefer the batch that expires soonest among valid stock.
- Support multi-batch fulfilment for a single request.
- Refuse the whole request (no silent partials) if total in-date stock is insufficient.
- Provide expiry visibility, daily housekeeping, robust CSV import, and low-stock re-order signals.

Three graded “twist” features were required:

1. Daily maintenance job (`POST /clock`).
2. Messy CSV import that tolerates real-world dirty data.
3. Re-order alerts written to an outbox when sellable stock crosses a threshold.

## 2. Technology choices

- **Flask** + blueprints for a small, readable modular structure.
- **MongoDB Atlas** (via `pymongo`) because document-oriented storage maps naturally to batches and because Atlas is easy to share for assessment.
- **mongomock** for unit tests so the suite runs without a live database.
- **python-dotenv** to keep credentials out of source.
- Plain Jinja2 templates + a single CSS file for a clean UI without a heavy front-end framework.

## 3. Data model

A single `batches` collection is sufficient:

```json
{
  "medicine_name": "Paracetamol",
  "batch_number": "P-001",
  "quantity": 50,
  "expiry_date": ISODate("..."),
  "quarantined": false,          // set by /clock
  "expiring_flagged": false,     // set by /clock
  "flagged_at": ISODate(...),
  "quarantined_at": ISODate(...)
}
```

A second collection `outbox` stores re-order messages for inspection / later delivery.

Indexes on `medicine_name` and `expiry_date` cover the common query patterns (search, FEFO sort, alerts).

## 4. Core design decisions

### 4.1 Shared helpers (`helpers.py`)

All “is this batch expired / sellable?” logic lives in one place:

- `today_start()` – midnight of the current local date.
- `is_expired()` / `batch_status()`.
- `sellable_match(extra=None)` – the canonical Mongo filter used by search, dispense, and re-order calculations.
- `serialize_batch()` – converts ObjectIds and datetimes into template/JSON-safe values.

This prevents subtle inconsistencies (e.g. one route treating the expiry day as still valid while another treats it as expired).

### 4.2 FEFO dispensing (`routes/dispensing.py`)

1. Query only sellable batches for the medicine, sorted by `expiry_date` ascending.
2. Build a plan of `(batch_id, take)` without writing anything.
3. If the plan does not fully cover the requested quantity → flash an error and abort.
4. Only then issue the `$inc` updates.
5. After a successful dispense, call `check_and_notify_if_needed`.

The two-phase approach guarantees atomicity at the application level and makes the plan easy to display to the pharmacist.

### 4.3 Daily maintenance (`POST /clock`)

- Flag batches whose expiry falls inside `[today, today + DAILY_QUARANTINE_DAYS]` and that are not already flagged.
- Quarantine every batch whose expiry is strictly before today.
- Collect the distinct medicines that were just quarantined and run the re-order scan on them (because quarantining removes them from sellable stock).

The endpoint is idempotent: already-flagged / already-quarantined documents are skipped by the filter.

### 4.4 Messy CSV import

Real CSVs contain:

- Empty cells
- Quantities written as `"10 units"`
- Dates in multiple formats
- Duplicate `(medicine, batch)` rows

The importer:

- Uses `csv.DictReader` for robustness.
- Extracts the first integer from the quantity field with a simple regex.
- Tries three common date formats and normalises to midnight.
- Accumulates quantities for the same key and keeps the later expiry.
- On existing DB documents performs an update (dedup path); otherwise inserts.
- Reports `imported`, `deduped`, `rejected` counts plus sample rows.

### 4.5 Re-order alerts

`get_sellable_stock` re-uses the same `sellable_match` filter, so quarantined and expired stock never inflate the count. When the total drops to ≤ threshold an outbox document is inserted. The check is called after every mutation that can reduce sellable stock (dispense, import, quarantine).

## 5. Testing strategy

Unit tests live next to the code and use `mongomock`:

- **test_dispense.py** – verifies FEFO ordering and the “insufficient stock → no plan” path.
- **test_importer.py** – exercises quantity/date parsers and a full messy CSV that produces the expected imported / rejected counts.
- **test_maintenance.py** – checks flagging, quarantine and idempotency of `/clock`.
- **test_notifications.py** – threshold crossing, quarantined stock exclusion, JSON outbox response.
- **test_search.py** – confirms expired batches are ignored.

Running `pytest -q` gives a fast green suite without network or credentials.

## 6. Issues encountered and how they were fixed

| Issue | Root cause | Fix |
|-------|------------|-----|
| Import errors for `routes.*` | Flat file layout vs. package imports | Documented the need for a `routes/` package (or import changes); tests inject the mock collections directly into the modules. |
| Expiry day treated inconsistently | Some code used `< today`, others `<=` | Centralised in `is_expired()`: expiry date itself is still valid (expires end-of-day). |
| Re-order alerts firing on expired stock | Sellable calculation did not exclude quarantined/expired | Always use `sellable_match()`. |
| Duplicate rows in CSV overwriting instead of summing | First implementation replaced the document | Buffer by `(medicine, batch)`, sum quantities, take max expiry, then upsert. |
| `/clock` not idempotent | Missing `$ne: True` guards | Added `expiring_flagged` / `quarantined` filters. |
| Templates looking for `static/style.css` while CSS sat in root | Flask default static folder | Documented the expected `static/` layout. |
| Tests accidentally talking to real Atlas | `config.py` ran at import time | Tests never import `config`; they replace the collection attributes on the route modules. |

## 7. Security & operational notes

- Credentials live only in `.env` (git-ignored).
- `app.secret_key` is a placeholder; must be changed for any non-dev deployment.
- No authentication is present (out of scope for the assessment).
- The outbox is a simple audit log; a production system would push to email/SMS/queue.

## 8. What would be improved next

- Move route modules into a proper `routes/` package and templates into `templates/`.
- Add authentication and role-based access.
- Make the maintenance job a real scheduled task (APScheduler / Celery / cloud cron) instead of a manual `POST /clock`.
- Soft-delete or archive quarantined batches instead of leaving them in the main collection.
- Add concurrency control (MongoDB transactions or optimistic versioning) for high-contention dispenses.

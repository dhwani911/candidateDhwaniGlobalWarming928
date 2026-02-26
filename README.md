# candidateDhwaniGlobalWarming928

Expedibox operates a distributed network of smart parcel lockers. Lockers emit events (door opened/closed, deposit, pickup, faults). A backend service must ingest events, validate them, maintain state, and expose an HTTP API for querying occupancy and audit trails.

## Table of Contents

- [How to run the API]
- [How to run tests](#features)
- [Short architecture and design rationale](#tech-stack)  


## How to run the API

1. Clone the Repository
```
git clone https://github.com/dhwani911/candidateDhwaniGlobalWarming928.git
cd candidateDhwaniGlobalWarming928
```
2. Create Virtual Environment
```
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```
3. Install Dependencies
```
pip install -r requirements.txt
```
4. Start the API
```
uvicorn app.main:app --reload
```
5. The API will be available at:
```
http://127.0.0.1:8000
```
5. Try the Swagger UI/OpenAPI
```
http://127.0.0.1:8000/docs
```
Swagger UI lets you explore endpoints and send test events interactively.

## How to run tests

The project uses pytest for automated tests.

Run all tests from project directory.
```
pytest -v 
```
### What gets tested

✔ Event schema / OpenAPI validation
✔ Idempotency
✔ Invalid transition rules
✔ Fault severity and degraded state logic
✔ Projection rebuild equivalence

If tests fail due to missing environment setup, ensure you activate the virtual environment and run from the project root.

## Short architecture and design rationale

#### Event Sourcing

The system is designed using the event sourcing pattern:

All changes are stored as discrete, immutable events. Events are appended to a JSONL file (events.jsonl).
The event log becomes the source of truth.

#### Persistence

Instead of a traditional database, Events are stored in an append-only JSON Lines (JSONL) file.
Each line represents one serialized event. 

#### Projection

A projection is computed in memory from the event log. It represents the current state of lockers and compartments.
Projection can be rebuilt from the entire log. A state_hash is calculated to verify correctness.

#### Idempotency

Duplicate events (same event_id) are ignored after first submission.

First submission → 202 Accepted

Duplicate → 200 OK (no reapplication)

#### Testability

The FastAPI app uses dependency injection via app.state, enabling:

Clean overrides in tests

Isolated state per test run

Reliable and deterministic behavior

### Key Endpoints

#### POST /events

Ingest an event into the system.

Returns:

202 when accepted and applied

200 for duplicate (idempotent)

409 for domain rule violations

422 for invalid payload

#### GET /lockers/{locker_id}

Returns a summary view of a locker and deterministic state_hash.

### Design Principles

Single source of truth: JSONL event log

Deterministic state: Projection can be reliably rebuilt

Clean architecture: Separation of API/domain/

Explicit serialization: UUIDs and datetime safely converted

Automated testing: Comprehensive behavior validation

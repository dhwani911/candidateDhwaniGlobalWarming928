"""
This test suite verifies:

1. OpenAPI validation behavior
2. Event idempotency
3. Invalid state transitions
4. Fault degradation + lineage rules
5. Projection rebuild equivalence

"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.structure.event_store import EventStore
from app.structure.projection import Projection


# -------------------------------------------------------------------
# Test Setup
# -------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    """
    Creates isolated event store + projection for this test.
    """

    test_file = tmp_path / "events.jsonl"

    store = EventStore(str(test_file))
    projection = Projection()

    # Inject into app state
    app.state.store = store
    app.state.projection = projection

    return TestClient(app)

def new_uuid():
    """Helper to generate unique UUIDs"""
    return str(uuid.uuid4())

# -------------------------------------------------------------------
# OpenAPI Validation Tests
# -------------------------------------------------------------------

def test_invalid_schema_returns_422(client):
    """
    If request does not match OpenAPI schema, FastAPI must return 422.
    """
    response = client.post("/events", json={"invalid": "data"})
    assert response.status_code == 422

# -------------------------------------------------------------------
# Event Idempotency Test
# -------------------------------------------------------------------

def test_duplicate_event_returns_200(client):
    """
    Same event_id sent twice:
    - First time → 202 Accepted
    - Second time → 200 Duplicate
    """

    event = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:00:00Z",
        "locker_id": "L1",
        "type": "CompartmentRegistered",
        "payload": {
            "compartment_id": "C1"
        }
    }

    r1 = client.post("/events", json=event)
    r2 = client.post("/events", json=event)

    assert r1.status_code == 202
    assert r2.status_code == 200


# -------------------------------------------------------------------
# Invalid State Transition Tests
# -------------------------------------------------------------------

def test_deposit_before_reservation_fails(client):
    """
    ParcelDeposited without ReservationCreated must return 409 (domain violation).
    """

    event = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:00:00Z",
        "locker_id": "L1",
        "type": "ParcelDeposited",
        "payload": {
            "reservation_id": "R1"
        }
    }

    response = client.post("/events", json=event)
    assert response.status_code == 409


def test_pickup_before_deposit_fails(client):
    """
    ReservationCreated → ParcelPickedUp directly should fail because deposit didn't happen.
    """

    reservation_id = "R2"

    register = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:00:00Z",
        "locker_id": "L1",
        "type": "CompartmentRegistered",
        "payload": {"compartment_id": "C1"}
    }

    create = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:01:00Z",
        "locker_id": "L1",
        "type": "ReservationCreated",
        "payload": {
            "compartment_id": "C1",
            "reservation_id": reservation_id
        }
    }

    pickup = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:02:00Z",
        "locker_id": "L1",
        "type": "ParcelPickedUp",
        "payload": {
            "reservation_id": reservation_id
        }
    }

    client.post("/events", json=register)
    client.post("/events", json=create)

    response = client.post("/events", json=pickup)

    assert response.status_code == 409

# -------------------------------------------------------------------
# Fault Degradation Tests
# -------------------------------------------------------------------

def test_fault_severity_degrades_compartment(client):
    """
    FaultReported with severity >= 3 should mark compartment degraded.
    """

    register = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:00:00Z",
        "locker_id": "L1",
        "type": "CompartmentRegistered",
        "payload": {"compartment_id": "C1"}
    }

    fault = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:01:00Z",
        "locker_id": "L1",
        "type": "FaultReported",
        "payload": {
            "compartment_id": "C1",
            "severity": 3
        }
    }

    client.post("/events", json=register)
    client.post("/events", json=fault)

    response = client.get("/lockers/L1")

    assert response.status_code == 200
    assert response.json()["degraded_compartments"] == 1


def test_invalid_fault_clear_reference(client):
    """
    Clearing a non-existing fault must return 409.
    """

    event = {
        "event_id": new_uuid(),
        "occurred_at": "2026-01-01T00:00:00Z",
        "locker_id": "L1",
        "type": "FaultCleared",
        "payload": {
            "reference_event_id": "non-existent-id"
        }
    }

    response = client.post("/events", json=event)
    assert response.status_code == 409

# -------------------------------------------------------------------
# Projection Equivalence Test
# -------------------------------------------------------------------

def test_projection_equivalence(client):
    """
    1. Send multiple valid events incrementally.
    2. Capture state_hash from running projection.
    3. Rebuild new projection from stored events.
    """

    events = [
        {
            "event_id": new_uuid(),
            "occurred_at": "2026-01-01T00:00:00Z",
            "locker_id": "L1",
            "type": "CompartmentRegistered",
            "payload": {"compartment_id": "C1"},
        },
        {
            "event_id": new_uuid(),
            "occurred_at": "2026-01-01T00:01:00Z",
            "locker_id": "L1",
            "type": "ReservationCreated",
            "payload": {
                "compartment_id": "C1",
                "reservation_id": "R1",
            },
        },
        {
            "event_id": new_uuid(),
            "occurred_at": "2026-01-01T00:02:00Z",
            "locker_id": "L1",
            "type": "ParcelDeposited",
            "payload": {"reservation_id": "R1"},
        },
        {
            "event_id": new_uuid(),
            "occurred_at": "2026-01-01T00:03:00Z",
            "locker_id": "L1",
            "type": "FaultReported",
            "payload": {
                "compartment_id": "C1",
                "severity": 2,
            },
        },
    ]

    # ------------------------------------------------------------------
    # STEP 1: Apply incrementally via API
    # ------------------------------------------------------------------

    for event in events:
        response = client.post("/events", json=event)
        assert response.status_code == 202

    # ------------------------------------------------------------------
    # STEP 2: Capture live projection state hash
    # ------------------------------------------------------------------

    response = client.get("/lockers/L1")
    assert response.status_code == 200

    incremental_hash = response.json()["state_hash"]

    # ------------------------------------------------------------------
    # STEP 3: Rebuild projection from disk
    # ------------------------------------------------------------------

    store = app.state.store
    rebuilt_projection = Projection()

    all_events = store.load_all()
    rebuilt_projection.rebuild(all_events)
    assert rebuilt_projection.lockers == app.state.projection.lockers
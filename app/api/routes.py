from fastapi import APIRouter, HTTPException, Response, status
from app.models.api_models import Event
from app.structure.event_store import EventStore
from app.structure.projection import Projection
from app.domain.errors import DomainError

router = APIRouter()
store = EventStore("events.jsonl")
projection = Projection()

@router.post("/events")
def ingest_event(event: Event):
    event_dict = event.model_dump(mode="json")

    try:
        if not store.append(event_dict):
            return Response(status_code=200)

        projection.apply(event_dict)
        return Response(status_code=202)

    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
@router.get("/lockers/{locker_id}")
def get_locker(locker_id: str):
    if locker_id not in projection.lockers:
        raise HTTPException(status_code=404)

    comps = projection.lockers[locker_id]

    return {
        "locker_id": locker_id,
        "compartments": len(comps),
        "active_reservations": sum(1 for c in comps.values() if c["active_reservation"]),
        "degraded_compartments": sum(1 for c in comps.values() if c["degraded"]),
        "state_hash": projection.state_hash(),
    }
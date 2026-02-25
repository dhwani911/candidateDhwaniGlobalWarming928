from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict
from uuid import UUID


class EventType(str, Enum):
    CompartmentRegistered = "CompartmentRegistered"
    ReservationCreated = "ReservationCreated"
    ParcelDeposited = "ParcelDeposited"
    ParcelPickedUp = "ParcelPickedUp"
    ReservationExpired = "ReservationExpired"
    FaultReported = "FaultReported"
    FaultCleared = "FaultCleared"


class Event(BaseModel):
    event_id: UUID
    occurred_at: datetime
    locker_id: str
    type: EventType
    payload: Dict


class LockerSummary(BaseModel):
    locker_id: str
    compartments: int
    active_reservations: int
    degraded_compartments: int
    state_hash: str


class CompartmentStatus(BaseModel):
    compartment_id: str
    degraded: bool
    active_reservation: Optional[str]


class ReservationState(str, Enum):
    CREATED = "CREATED"
    DEPOSITED = "DEPOSITED"
    PICKED_UP = "PICKED_UP"
    EXPIRED = "EXPIRED"


class ReservationStatus(BaseModel):
    reservation_id: str
    status: ReservationState
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime


EventType = Literal[
    "CompartmentRegistered",
    "ReservationCreated",
    "ReservationExpired",
    "ParcelDeposited",
    "ParcelPickedUp",
    "FaultReported",
    "FaultCleared",
]


@dataclass(frozen=True)
class Event:
    event_id: str
    locker_id: str
    compartment_id: str
    type: EventType
    timestamp: datetime
    payload: dict
import hashlib
import json
from collections import defaultdict
from typing import Dict, Optional
from app.domain.errors import InvalidTransition, FaultReferenceError


class Projection:

    def __init__(self):
        self.lockers = defaultdict(dict)
        self.reservations = {}
        self.faults = {}

    def rebuild(self, events):
        self.__init__()
        for event in events:
            self.apply(event)

    def apply(self, event: Dict):

        locker_id = event["locker_id"]
        event_type = event["type"]
        payload = event["payload"]

        if event_type == "CompartmentRegistered":
            comp_id = payload["compartment_id"]
            self.lockers[locker_id][comp_id] = {
                "active_reservation": None,
                "degraded": False,
                "faults": set()
            }

        elif event_type == "ReservationCreated":
            comp_id = payload["compartment_id"]
            reservation_id = payload["reservation_id"]

            compartment = self._get_compartment(locker_id, comp_id)

            if compartment["degraded"]:
                raise InvalidTransition("Compartment degraded")

            if compartment["active_reservation"]:
                raise InvalidTransition("Reservation already exists")

            compartment["active_reservation"] = reservation_id
            self.reservations[reservation_id] = "CREATED"

        elif event_type == "ParcelDeposited":
            reservation_id = payload["reservation_id"]
            self._ensure_reservation_state(reservation_id, "CREATED")
            self.reservations[reservation_id] = "DEPOSITED"

        elif event_type == "ParcelPickedUp":
            reservation_id = payload["reservation_id"]
            self._ensure_reservation_state(reservation_id, "DEPOSITED")
            self.reservations[reservation_id] = "PICKED_UP"
            self._clear_reservation_from_compartment(locker_id, reservation_id)

        elif event_type == "ReservationExpired":
            reservation_id = payload["reservation_id"]
            self._ensure_reservation_state(reservation_id, "CREATED")
            self.reservations[reservation_id] = "EXPIRED"
            self._clear_reservation_from_compartment(locker_id, reservation_id)

        elif event_type == "FaultReported":
            comp_id = payload["compartment_id"]
            severity = payload["severity"]

            compartment = self._get_compartment(locker_id, comp_id)
            self.faults[event["event_id"]] = event
            compartment["faults"].add(event["event_id"])

            if severity >= 3:
                compartment["degraded"] = True

        elif event_type == "FaultCleared":
            ref = payload["reference_event_id"]
            if ref not in self.faults:
                raise FaultReferenceError("Invalid fault reference")

            fault_event = self.faults[ref]
            comp_id = fault_event["payload"]["compartment_id"]
            compartment = self._get_compartment(locker_id, comp_id)

            if ref not in compartment["faults"]:
                raise FaultReferenceError("Fault already cleared")

            compartment["faults"].remove(ref)

            # recompute degraded
            compartment["degraded"] = any(
                self.faults[f]["payload"]["severity"] >= 3
                for f in compartment["faults"]
            )

    def _get_compartment(self, locker_id, comp_id):
        if comp_id not in self.lockers[locker_id]:
            raise InvalidTransition("Compartment not registered")
        return self.lockers[locker_id][comp_id]

    def _ensure_reservation_state(self, reservation_id, expected):
        if self.reservations.get(reservation_id) != expected:
            raise InvalidTransition("Invalid reservation state")

    def _clear_reservation_from_compartment(self, locker_id, reservation_id):
        for comp in self.lockers[locker_id].values():
            if comp["active_reservation"] == reservation_id:
                comp["active_reservation"] = None

    def state_hash(self) -> str:
        """
        Deterministic hash based ONLY on API-visible state.
        """

        normalized = {}

        for locker_id in sorted(self.lockers.keys()):
            normalized[locker_id] = {}

            for comp_id in sorted(self.lockers[locker_id].keys()):
                comp = self.lockers[locker_id][comp_id]

                normalized[locker_id][comp_id] = {
                    "active_reservation": comp["active_reservation"],
                    "degraded": comp["degraded"],
                }

        serialized = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
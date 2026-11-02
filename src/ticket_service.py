"""In-memory model and sample-data generation for Message Rate Control tickets.

Kept separate from the activities so the state machine (pending -> help_requested
-> actioned/expired) and the countdown bookkeeping can be understood and tested
without pulling in the Symphony BDK activity plumbing.
"""
import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

TICKET_EXPIRY_SECONDS = 15
COUNTDOWN_TICK_SECONDS = 5

TRADERS = ["Lyosja", "Amrai", "Denholt", "Sferra"]
ALGO_NAMES = ["Iceberg", "Sniper", "VWAP", "Pegged"]
INSTRUMENTS = ["WNM6", "FGBLM6", "ESU6", "ZNU6"]
FLOWS = ["Order Submission", "Order Amendment", "Order Cancellation"]
BREACH_REASONS = [
    "Messages sent/received exceeds limit",
    "Order-to-trade ratio exceeded",
    "Duplicate order burst detected",
]

# (value, label) pairs rendered as <option> elements in the help form dropdown.
HELP_TOPICS = [
    ("breach_threshold", "Why did this breach the rate limit?"),
    ("false_positive", "I believe this is a false positive"),
    ("algo_config", "Algo configuration / parameters question"),
    ("other", "Something else"),
]

DECISION_ACTIONS = {
    "acknowledge": "Acknowledge - Investigating",
    "not_disorderly": "Not Disorderly",
    "trading_incident": "Trading Incident",
    "potential_disorderly": "Potential Disorderly",
}


def generate_ticket_id() -> str:
    return f"RTM-{uuid.uuid4().hex[:8].upper()}"


def generate_ticket_fields() -> dict:
    """Random sample data resembling a real Message Rate Control alert."""
    return {
        "trader": random.choice(TRADERS),
        "algo_name": random.choice(ALGO_NAMES),
        "instrument": random.choice(INSTRUMENTS),
        "entity": f"EM-{random.randint(250100, 250999)}-{random.randint(1000, 9999)}",
        "flow": random.choice(FLOWS),
        "reason": random.choice(BREACH_REASONS),
    }


@dataclass
class Ticket:
    """A live Message Rate Control ticket and its countdown/help-flow state."""

    ticket_id: str
    stream_id: str
    message_id: str
    trader: str
    algo_name: str
    instrument: str
    entity: str
    flow: str
    reason: str
    status: str = "pending"  # pending | help_requested | actioned | expired
    remaining_seconds: int = TICKET_EXPIRY_SECONDS
    timer_task: Optional[asyncio.Task] = field(default=None, repr=False)

    def cancel_timer(self) -> None:
        """Stops the countdown. Used both when the ticket is actioned and when the
        Help flow is launched - the countdown must not expire the ticket while the
        user is filling out the help form."""
        if self.timer_task is not None and not self.timer_task.done():
            self.timer_task.cancel()
        self.timer_task = None

    def as_template_context(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "trader": self.trader,
            "algo_name": self.algo_name,
            "instrument": self.instrument,
            "entity": self.entity,
            "flow": self.flow,
            "reason": self.reason,
            "remaining_seconds": self.remaining_seconds,
        }


class TicketRegistry:
    """In-memory store of live tickets, keyed by ticket id."""

    def __init__(self):
        self._tickets: dict[str, Ticket] = {}

    def add(self, ticket: Ticket) -> None:
        self._tickets[ticket.ticket_id] = ticket

    def get(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def remove(self, ticket_id: str) -> None:
        self._tickets.pop(ticket_id, None)

"""Data types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_on_vendor", "awaiting_approval", "resolved"]


@dataclass
class RunBudget:
    """Counters shared by every agent in one team run."""

    delegations: int = 0


@dataclass
class TeamDeps:
    """Run context passed to every agent. `chain` is the delegation path so
    far (e.g. ["boss", "inventory"]) and is how the team stops loops."""

    run_id: str
    chain: list[AgentName]
    budget: RunBudget = field(default_factory=RunBudget)

    @property
    def agent(self) -> AgentName:
        return self.chain[-1]

    @property
    def depth(self) -> int:
        return len(self.chain) - 1


class PaymentRequest(BaseModel):
    """A payment an agent wants made. Agents never pay; a human approves or
    rejects each request in the dashboard."""

    kind: Literal["invoice", "rent", "purchase_order"]
    ref_id: int | None = Field(None, description="invoices.id or leases.id; null for a new PO")
    payee: str
    amount: float = Field(gt=0)
    due_date: str | None = None
    reason: str = Field(description="Why this should be paid, citing the tool facts")
    priority: int = Field(ge=1, description="1 = pay first")
    unblocks_tickets: list[int] = []


class RateApproval(BaseModel):
    """A discount the team recommends. Like a payment, only the owner can
    approve it, which they do in the dashboard."""

    ticket_id: int
    sku: str
    qty: int = Field(gt=0)
    discount_pct: float = Field(gt=0, lt=100)
    unit_price: float
    order_margin: float
    reason: str


class Fact(BaseModel):
    """One number or status pulled from an MCP tool, with where it came from."""

    statement: str
    source_tool: str


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities and Customer Service hand back."""

    agent: AgentName
    ticket_ids: list[int]
    summary: str = Field(description="Two to four sentences, plain English")
    facts: list[Fact] = Field(description="Every number used, with its MCP tool")
    actions_taken: list[str] = Field(description="Ticket updates or delegations actually made")
    payment_requests: list[PaymentRequest] = []
    recommendations: list[str] = []
    customer_message: str | None = Field(None, description="Draft reply to the requester, if any")
    needs_human: list[str] = Field([], description="Decisions only a person may make")


class TicketOutcome(BaseModel):
    ticket_id: int
    owner: AgentName
    status: TicketStatus
    decision: str
    customer_message: str | None = None
    next_steps: list[str] = []


class TeamReport(BaseModel):
    """Boss's final answer for one run of the team."""

    run_summary: str
    tickets: list[TicketOutcome]
    payment_queue: list[PaymentRequest] = Field(
        description="All payment requests for human approval, in priority order"
    )
    rate_approvals: list[RateApproval] = Field(
        [], description="Discounts still waiting for the owner's approval"
    )
    cash_on_hand: float
    cash_after_payment_queue: float
    deferred: list[str] = Field([], description="Work held back because cash or stock ran out")
    risks: list[str] = []

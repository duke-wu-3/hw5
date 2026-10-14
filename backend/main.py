"""FastAPI backend for the Campus Customs dashboard.

Run from backend/:  uvicorn main:app --port 8000

Agents only prepare payments. POST /payments/approve is the one place cash
actually moves, and only after a human clicks approve in the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_ai.usage import RunUsage

import audit
from agents.team import MODEL_NAME, run_agent
from models import TeamDeps, TeamReport

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
CASH_ACCOUNT = "checking"

app = FastAPI(title="Campus Customs backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One team run (or reset) at a time, so two runs never write the same tickets.
_busy = asyncio.Lock()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(WORKING_DB)
    conn.row_factory = sqlite3.Row
    return conn


def shop_today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=y, month=m).isoformat()


# ---------- tickets ----------


@app.get("/tickets")
def list_tickets() -> dict:
    """All three tickets, each marked open or resolved (plus its detailed status)."""
    with connect() as conn:
        today = shop_today(conn)
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    tickets = [
        {**dict(r), "state": "resolved" if r["status"] == "resolved" else "open"} for r in rows
    ]
    return {"date_today": today, "tickets": tickets}


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int) -> dict:
    """Run the agent team (Boss first, delegating as needed) on one ticket."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            raise HTTPException(404, f"No ticket with id={ticket_id}.")
    if _busy.locked():
        raise HTTPException(409, "The team is already running. Wait for it to finish.")
    async with _busy:
        deps = TeamDeps(run_id=uuid.uuid4().hex[:12], chain=["boss"])
        prompt = (
            f"Work ticket {ticket_id} only. Look at other tickets only where they share "
            "cash, stock or a vendor with it. Give me the team report."
        )
        try:
            report: TeamReport = await run_agent("boss", prompt, deps, usage=RunUsage())
        except Exception as exc:  # already written to the audit trail by run_agent
            raise HTTPException(502, f"Team run {deps.run_id} failed: {exc}") from exc
        status = record_final_status(ticket_id, report, deps.run_id)
    return {
        "run_id": deps.run_id,
        "ticket_id": ticket_id,
        "model": MODEL_NAME,
        "status": status,
        "report": report.model_dump(),
    }


def record_final_status(ticket_id: int, report: TeamReport, run_id: str) -> str:
    """Write Boss's final status for the ticket it worked, so the DB matches
    the report even if Boss skipped update_ticket. A ticket can't be
    resolved while a payment or rate that unblocks it still waits for a human."""
    outcome = next((t for t in report.tickets if t.ticket_id == ticket_id), None)
    if outcome is None:
        return "unchanged"
    status = outcome.status
    unsigned = [p for p in report.payment_queue if ticket_id in p.unblocks_tickets] + [
        r for r in report.rate_approvals if r.ticket_id == ticket_id
    ]
    if status == "resolved" and unsigned:
        status = "awaiting_approval"
    with connect() as conn:
        today = shop_today(conn)
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        line = f"[{today} boss] Final status from team run {run_id}: {status}. {outcome.decision}"
        notes = f"{row['notes']}\n{line}" if row["notes"] else line
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    audit.append({"run_id": run_id, "agent": "boss", "chain": "boss", "kind": "ticket_status",
                  "message": f"Ticket {ticket_id}: {row['status']} -> {status}", "ticket_id": ticket_id,
                  "previous_status": row["status"], "status": status})
    return status


# ---------- agent events ----------


def _said(entry: dict) -> str | None:
    if entry.get("text"):
        return "\n".join(entry["text"])
    if entry.get("thinking"):
        return "\n".join(entry["thinking"])
    out = entry.get("output")
    if isinstance(out, dict):
        return out.get("run_summary") or out.get("summary")
    return entry.get("prompt") or entry.get("error") or entry.get("message")


@app.get("/events")
def list_events(after: int = -1, limit: int = 100, run_id: str | None = None) -> dict:
    """Recent audit-trail steps: what each agent said and which tools it used.

    Poll with ?after=<last index you saw> to get only new events.
    """
    path = audit.AUDIT_PATH
    rows: list[dict] = []
    if path.exists() and path.stat().st_size > 0:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []  # mid-write; the next poll will catch up
    events = []
    for i, e in enumerate(rows):
        if i <= after or (run_id and e.get("run_id") != run_id):
            continue
        events.append(
            {
                "index": i,
                "time": e.get("time"),
                "run_id": e.get("run_id"),
                "agent": e.get("agent"),
                "chain": e.get("chain"),
                "kind": e.get("kind"),
                "said": _said(e),
                "tool_calls": [
                    {"tool": c.get("tool"), "args": c.get("args")} for c in e.get("tool_calls", [])
                ],
                "tool_results": [r.get("tool") for r in e.get("tool_results", []) if r.get("tool")],
            }
        )
    return {"total": len(rows), "events": events[-limit:]}


# ---------- money ----------


class ApprovePayment(BaseModel):
    """A payment request from the team's payment_queue, approved by a person."""

    kind: Literal["invoice", "rent", "purchase_order"]
    ref_id: int | None = Field(None, description="invoices.id or leases.id; vendor id for a PO")
    payee: str
    amount: float = Field(gt=0)
    approved_by: str = Field(min_length=1)
    unblocks_tickets: list[int] = []


@app.post("/payments/approve")
def approve_payment(req: ApprovePayment) -> dict:
    """The only route that changes cash. Checks the request against the
    database, refuses anything over the balance, then pays and logs it."""
    with connect() as conn:
        today = shop_today(conn)
        cash = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)
        ).fetchone()["balance"]
        amount = round(req.amount, 2)
        if amount > cash:
            raise HTTPException(409, f"${amount:,.2f} is more than the ${cash:,.2f} in {CASH_ACCOUNT}.")

        ref_id = req.ref_id
        if req.kind == "invoice":
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                raise HTTPException(404, f"No invoice with id={ref_id}.")
            if inv["status"] != "open":
                raise HTTPException(409, f"Invoice {ref_id} is already {inv['status']}.")
            if amount != round(inv["amount"], 2):
                raise HTTPException(409, f"Invoice {ref_id} is ${inv['amount']:,.2f}, not ${amount:,.2f}.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            effect = f"Invoice {ref_id} marked paid."
        elif req.kind == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                raise HTTPException(404, f"No lease with id={ref_id}.")
            if amount != round(lease["monthly_rent"], 2):
                raise HTTPException(409, f"Lease {ref_id} rent is ${lease['monthly_rent']:,.2f}, not ${amount:,.2f}.")
            next_due = add_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, ref_id))
            effect = f"Lease {ref_id} rent paid; next due {next_due}."
        else:  # purchase_order
            vendor = conn.execute(
                "SELECT * FROM vendors WHERE id = ? OR lower(name) = lower(?)", (ref_id, req.payee)
            ).fetchone()
            if vendor is None:
                raise HTTPException(404, f"No vendor matching '{req.payee}'.")
            blocking = conn.execute(
                "SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor["id"],)
            ).fetchall()
            if blocking:
                ids = ", ".join(str(r["id"]) for r in blocking)
                raise HTTPException(409, f"{vendor['name']} has open invoice(s) {ids}; pay those first.")
            ref_id = vendor["id"]
            effect = f"Purchase order paid to {vendor['name']} (vendor {ref_id})."

        new_balance = round(cash - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ? WHERE name = ?", (new_balance, CASH_ACCOUNT)
        )
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req.kind, ref_id, amount, CASH_ACCOUNT, today, req.approved_by),
        )
        payment_id = cur.lastrowid

        # Note the payment on linked tickets; paying rent closes the rent ticket.
        ticket_ids = set(req.unblocks_tickets)
        if req.kind == "rent":
            rent_tickets = conn.execute("SELECT id FROM tickets WHERE lease_id = ?", (ref_id,)).fetchall()
            ticket_ids |= {r["id"] for r in rent_tickets}
        for tid in sorted(ticket_ids):
            row = conn.execute("SELECT type, status, notes FROM tickets WHERE id = ?", (tid,)).fetchone()
            if row is None:
                continue
            line = f"[{today} human:{req.approved_by}] Approved payment #{payment_id}: ${amount:,.2f} to {req.payee}. {effect}"
            notes = f"{row['notes']}\n{line}" if row["notes"] else line
            status = "resolved" if req.kind == "rent" and row["type"] == "rent_notice" else row["status"]
            conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, tid))

    audit.append(
        {
            "run_id": None,
            "agent": "human",
            "chain": "human",
            "kind": "payment_approved",
            "message": f"{req.approved_by} approved ${amount:,.2f} to {req.payee}. {effect}",
            "payment": {"id": payment_id, **req.model_dump(), "ref_id": ref_id},
            "balance_after": new_balance,
        }
    )
    return {
        "payment_id": payment_id,
        "effect": effect,
        "balance_before": cash,
        "balance_after": new_balance,
        "tickets_noted": sorted(ticket_ids),
    }


class ApproveRate(BaseModel):
    """A group discount from the team's rate_approvals, approved by a person."""

    ticket_id: int
    sku: str
    qty: int = Field(gt=0)
    discount_pct: float = Field(gt=0, lt=100)
    approved_by: str = Field(min_length=1)


@app.post("/pricing/approve")
def approve_rate(req: ApproveRate) -> dict:
    """The owner signs off a discount. No cash moves; the approval is noted on
    the ticket (where the team reads it on its next run) and in the audit trail."""
    with connect() as conn:
        today = shop_today(conn)
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (req.ticket_id,)).fetchone()
        if ticket is None:
            raise HTTPException(404, f"No ticket with id={req.ticket_id}.")
        if ticket["sku"] != req.sku or (ticket["qty"] and ticket["qty"] != req.qty):
            raise HTTPException(409, f"Ticket {req.ticket_id} is for {ticket['qty']} x {ticket['sku']}.")
        price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (req.sku,)).fetchone()
        if price is None:
            raise HTTPException(404, f"No pricing row for sku={req.sku}.")
        unit_price = round(price["list_price"] * (1 - req.discount_pct / 100), 2)
        if unit_price < price["unit_cost"]:
            raise HTTPException(409, f"${unit_price:,.2f} is below the ${price['unit_cost']:,.2f} unit cost.")
        total = round(unit_price * req.qty, 2)
        margin = round((unit_price - price["unit_cost"]) * req.qty, 2)
        line = (f"[{today} human:{req.approved_by}] Approved group rate: {req.discount_pct:g}% off "
                f"${price['list_price']:,.2f} list = ${unit_price:,.2f} each x {req.qty} = ${total:,.2f} "
                f"(margin ${margin:,.2f}). No cash moved.")
        notes = f"{ticket['notes']}\n{line}" if ticket["notes"] else line
        conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, req.ticket_id))
    audit.append({"run_id": None, "agent": "human", "chain": "human", "kind": "rate_approved",
                  "message": line, "rate": {**req.model_dump(), "unit_price": unit_price,
                                            "order_total": total, "order_margin": margin}})
    return {"effect": f"Group rate approved: {req.discount_pct:g}% = ${unit_price:,.2f} each.",
            "unit_price": unit_price, "order_total": total, "order_margin": margin}


@app.get("/cash")
def get_cash() -> dict:
    """Current checking balance from cash_accounts."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()
    return dict(row)


# ---------- reset ----------


@app.post("/reset")
async def reset() -> dict[str, Any]:
    """Copy the pristine campus_customs.db over campus_customs_new.db.
    The audit trail is append-only and is not wiped; a reset entry marks it."""
    if _busy.locked():
        raise HTTPException(409, "The team is running. Reset after it finishes.")
    async with _busy:
        src = sqlite3.connect(ORIGINAL_DB)
        dst = sqlite3.connect(WORKING_DB)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
    audit.append({"run_id": None, "agent": "human", "chain": "human", "kind": "reset",
                  "message": "Working database reset to the original values."})
    return {"reset": True, **get_cash(), "tickets": list_tickets()["tickets"]}

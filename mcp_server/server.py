"""Campus Customs MCP server.

Exposes shop-database tools to the agent team. Every tool reads
data/campus_customs_new.db (the working copy) and returns only values
stored in the database or arithmetic on them. Missing records return an
error instead of a guess.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def shop_today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today, never the real clock."""
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    return date.fromisoformat(row["date_today"])


@mcp.tool
def get_stock_and_pricing(sku: str, size: str, qty_requested: int) -> dict:
    """Check on-hand stock for one SKU and size against a requested quantity,
    and return its unit cost and list price.

    Use for orders and discount requests: shows the shortfall and the cost
    floor below which a discount loses money.
    """
    with connect() as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            return {"error": f"No inventory row for sku={sku!r}, size={size!r}."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    on_hand = item["qty"]
    result = {
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "location": item["location"],
        "qty_on_hand": on_hand,
        "qty_requested": qty_requested,
        "shortfall": max(qty_requested - on_hand, 0),
    }
    if price is None:
        result["pricing"] = None
        result["pricing_note"] = f"No pricing row for sku={sku!r}."
    else:
        result["unit_cost"] = price["unit_cost"]
        result["list_price"] = price["list_price"]
        result["margin_per_unit_at_list"] = round(price["list_price"] - price["unit_cost"], 2)
    return result


@mcp.tool
def get_vendor_invoices(vendor_id: int) -> dict:
    """Return a vendor's details and every invoice on file for it, with
    days overdue measured from desk.date_today.

    A vendor will not ship new product while it has an open unpaid invoice,
    so check this before planning any restock.
    """
    with connect() as conn:
        today = shop_today(conn)
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if vendor is None:
            return {"error": f"No vendor with id={vendor_id}."}
        invoices = conn.execute(
            "SELECT id, amount, due_date, status, description FROM invoices "
            "WHERE vendor_id = ? ORDER BY due_date",
            (vendor_id,),
        ).fetchall()

    rows = []
    for inv in invoices:
        days_past_due = (today - date.fromisoformat(inv["due_date"])).days
        rows.append(
            {
                "invoice_id": inv["id"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "status": inv["status"],
                "description": inv["description"],
                "days_overdue": days_past_due if inv["status"] == "open" and days_past_due > 0 else 0,
            }
        )
    open_invoices = [r for r in rows if r["status"] == "open"]
    return {
        "date_today": today.isoformat(),
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "invoices": rows,
        "open_balance": round(sum(r["amount"] for r in open_invoices), 2),
        "can_ship": not open_invoices,
    }


@mcp.tool
def get_lease_and_cash(lease_id: int) -> dict:
    """Return a lease's rent and next due date, days until due from
    desk.date_today, and whether cash on hand covers the rent.
    """
    with connect() as conn:
        today = shop_today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}."}
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    total_cash = round(sum(a["balance"] for a in accounts), 2)
    rent = lease["monthly_rent"]
    return {
        "date_today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
        "notes": lease["notes"],
        "cash_accounts": [dict(a) for a in accounts],
        "total_cash": total_cash,
        "cash_covers_rent": total_cash >= rent,
        "cash_after_rent": round(total_cash - rent, 2),
    }


# --- Problem 5 tools: ticket queue, cash planning, restock and discount math ---

TICKET_STATUSES = ("open", "in_progress", "waiting_on_vendor", "awaiting_approval", "resolved")


def ticket_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved, oldest first, with the SKU,
    lease and invoice ids that link it to the rest of the shop data.

    Boss starts every run here to see the work queue.
    """
    with connect() as conn:
        today = shop_today(conn)
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {
        "date_today": today.isoformat(),
        "count": len(rows),
        "tickets": [ticket_dict(r) for r in rows],
    }


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket with all its fields, including the running notes
    trail that agents append to with update_ticket.
    """
    with connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"error": f"No ticket with id={ticket_id}."}
    return ticket_dict(row)


@mcp.tool
def get_cash_position(horizon_days: int = 30) -> dict:
    """Show cash on hand against every open vendor invoice and every lease
    payment due within horizon_days of desk.date_today.

    Lists obligations most-urgent first (overdue, then soonest due) with a
    running cash balance, so Accounting can see exactly where money runs out.
    No money comes in, so cash_accounts is the only source of funds.
    """
    with connect() as conn:
        today = shop_today(conn)
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()
        invoices = conn.execute(
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.description "
            "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"
        ).fetchall()
        leases = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases"
        ).fetchall()

    obligations = []
    for inv in invoices:
        days = (date.fromisoformat(inv["due_date"]) - today).days
        obligations.append(
            {
                "kind": "invoice",
                "ref_id": inv["id"],
                "payee": inv["vendor_name"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "days_until_due": days,
                "overdue": days < 0,
                "description": inv["description"],
            }
        )
    for lease in leases:
        days = (date.fromisoformat(lease["next_due"]) - today).days
        if days <= horizon_days:
            obligations.append(
                {
                    "kind": "rent",
                    "ref_id": lease["id"],
                    "payee": lease["landlord"],
                    "amount": lease["monthly_rent"],
                    "due_date": lease["next_due"],
                    "days_until_due": days,
                    "overdue": days < 0,
                    "description": f"Rent for {lease['space_name']}",
                }
            )
    obligations.sort(key=lambda o: o["days_until_due"])

    cash = round(sum(a["balance"] for a in accounts), 2)
    running = cash
    for o in obligations:
        running = round(running - o["amount"], 2)
        o["cash_after_if_paid_in_order"] = running
    total_due = round(sum(o["amount"] for o in obligations), 2)
    return {
        "date_today": today.isoformat(),
        "horizon_days": horizon_days,
        "cash_accounts": [dict(a) for a in accounts],
        "total_cash": cash,
        "obligations": obligations,
        "total_obligations": total_due,
        "cash_after_all_obligations": round(cash - total_due, 2),
        "can_cover_all": cash >= total_due,
    }


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead time and open invoice
    balance, plus whether it will ship today (no open invoices).

    Use to pick which vendor can restock an item before quoting it.
    """
    with connect() as conn:
        vendors = conn.execute("SELECT id, name, specialty, lead_days FROM vendors").fetchall()
        open_rows = conn.execute(
            "SELECT vendor_id, COUNT(*) AS n, SUM(amount) AS total FROM invoices "
            "WHERE status = 'open' GROUP BY vendor_id"
        ).fetchall()
    open_by_vendor = {r["vendor_id"]: r for r in open_rows}
    rows = []
    for v in vendors:
        o = open_by_vendor.get(v["id"])
        rows.append(
            {
                **dict(v),
                "open_invoice_count": o["n"] if o else 0,
                "open_balance": round(o["total"], 2) if o else 0.0,
                "can_ship": o is None,
            }
        )
    return {"vendors": rows}


@mcp.tool
def quote_restock(sku: str, size: str, qty: int, vendor_id: int) -> dict:
    """Cost a restock of qty units of one SKU and size from one vendor.

    Returns current stock, cost at pricing.unit_cost, the vendor lead time
    and arrival date from desk.date_today, and whether the vendor is blocked
    by an open invoice. This is a quote only: nothing is ordered or paid.
    """
    if qty <= 0:
        return {"error": "qty must be a positive whole number."}
    with connect() as conn:
        today = shop_today(conn)
        item = conn.execute(
            "SELECT name, qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        blocking = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
            (vendor_id,),
        ).fetchall()
    if item is None:
        return {"error": f"No inventory row for sku={sku!r}, size={size!r}."}
    if price is None:
        return {"error": f"No pricing row for sku={sku!r}."}
    if vendor is None:
        return {"error": f"No vendor with id={vendor_id}."}

    return {
        "date_today": today.isoformat(),
        "sku": sku,
        "name": item["name"],
        "size": size,
        "qty_on_hand": item["qty"],
        "qty_to_order": qty,
        "unit_cost": price["unit_cost"],
        "total_cost": round(qty * price["unit_cost"], 2),
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "vendor_specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "arrives_if_ordered_today": (today + timedelta(days=vendor["lead_days"])).isoformat(),
        "can_ship": not blocking,
        "blocking_invoices": [dict(b) for b in blocking],
    }


@mcp.tool
def check_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Test a proposed percentage discount off list price for qty units.

    Returns the discounted unit price, margin per unit and in total, margin
    as a percent of the discounted price, and the largest discount that
    still sells at or above pricing.unit_cost. above_cost is false when the
    discount would sell below cost.
    """
    if not 0 <= discount_pct < 100:
        return {"error": "discount_pct must be between 0 and 100."}
    if qty <= 0:
        return {"error": "qty must be a positive whole number."}
    with connect() as conn:
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if price is None:
        return {"error": f"No pricing row for sku={sku!r}."}

    cost, list_price = price["unit_cost"], price["list_price"]
    unit_price = round(list_price * (1 - discount_pct / 100), 2)
    margin = round(unit_price - cost, 2)
    return {
        "sku": sku,
        "qty": qty,
        "unit_cost": cost,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "discounted_unit_price": unit_price,
        "margin_per_unit": margin,
        "margin_pct_of_price": round(margin / unit_price * 100, 1) if unit_price else None,
        "order_revenue": round(unit_price * qty, 2),
        "order_cost": round(cost * qty, 2),
        "order_margin": round(margin * qty, 2),
        "max_discount_pct_at_cost": round((1 - cost / list_price) * 100, 1),
        "above_cost": margin > 0,
    }


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str, agent: str) -> dict:
    """Set a ticket's status and append a signed note to its notes trail.

    status must be one of: open, in_progress, waiting_on_vendor,
    awaiting_approval, resolved. Existing notes are kept; the new note is
    added as a new line prefixed with desk.date_today and the agent name.
    This is the only tool that writes, and it only touches the tickets table.
    """
    if status not in TICKET_STATUSES:
        return {"error": f"status must be one of {', '.join(TICKET_STATUSES)}."}
    note = note.strip()
    if not note:
        return {"error": "note must not be empty."}
    with connect() as conn:
        today = shop_today(conn)
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"error": f"No ticket with id={ticket_id}."}
        line = f"[{today.isoformat()} {agent}] {note[:500]}"
        notes = f"{row['notes']}\n{line}" if row["notes"] else line
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id)
        )
    return {
        "ticket_id": ticket_id,
        "previous_status": row["status"],
        "status": status,
        "note_added": line,
    }


if __name__ == "__main__":
    mcp.run()

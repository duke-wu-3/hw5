# Campus Customs Harness

Running reference for the agent team. Source: `data/campus_customs.db` (original, read-only).
Agents and the MCP server work against `data/campus_customs_new.db`.

## Tables

### desk (1 row)
Fields: `date_today`, `notes`
Why it matters: `date_today` (2026-08-31) is the shop's "today". All overdue and due-soon checks use it, not the real clock.

### tickets (3 rows)
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
Why it matters: This is the work queue. Boss reads each open ticket and routes it, and the optional `sku`, `lease_id` and `invoice_id` fields link it to the rest of the data.

### inventory (10 rows)
Fields: `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`)
Why it matters: Inventory checks stock by SKU and size here to find shortfalls.

### pricing (4 rows)
Fields: `sku`, `unit_cost`, `list_price`
Why it matters: Accounting uses it for margin checks on discounts and to cost restock purchase orders.

### vendors (3 rows)
Fields: `id`, `name`, `specialty`, `lead_days`
Why it matters: Inventory picks which vendor can restock an item (by specialty) and when it would arrive (`lead_days`).

### invoices (1 row)
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
Why it matters: A vendor with an `open` invoice will not ship new product. Accounting watches this table for overdue bills.

### leases (1 row)
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
Why it matters: Facilities owns this table. It shows rent amounts and due dates for the shop space.

### cash_accounts (1 row)
Fields: `name`, `balance`, `date`
Why it matters: This is the only source of money. The pay tool must refuse any payment larger than `balance`, and no money comes in.

### payments (0 rows)
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
Why it matters: This is the audit log of payments a human approved. Each one is written here alongside the cash, invoice or lease update.

## Starting state (desk.date_today = 2026-08-31)

- Cash: checking $3,400.00
- Invoice 501: Bulldog Print Co (vendor 1), $840.00, due 2026-08-28, **open, overdue by 3 days** ("Rush reprint CC-TEE-WHITE S")
- Lease 1: Chapel Street shop, Elm City Properties, $2,400.00, next due 2026-09-02 (in 2 days)
- Zero stock: CC-TEE-WHITE S, CC-MUG-CREST OS

## Open tickets and links

| Ticket | Type | Ask | Links to | What the data shows |
|---|---|---|---|---|
| 101 | customer_order | Tauhid Zaman wants 1 Bulldog tee, size S | inventory (CC-TEE-WHITE S), invoice 501, vendor 1, pricing | Stock is 0. The tee restock comes from Bulldog Print Co (apparel, 5-day lead time), but invoice 501 for $840 is open and overdue, so the vendor won't ship until it's paid. |
| 102 | rent_notice | Elm City Properties: rent due in 2 days | lease 1, cash_accounts | $2,400 is due 2026-09-02. Paying it needs human approval and leaves $1,000 if nothing else is paid. |
| 103 | price_override | Yale AI Club wants 20 hoodies, size M, at a bulk discount | inventory (CC-HOOD-NAVY M), pricing, vendor 1, invoice 501 | Only 8 in stock, so 12 are short. A restock from Bulldog Print Co costs 12 × $22 = $264 and is also blocked by invoice 501. Unit cost $22 and list price $58 set the discount floor. |

## Cross-ticket constraints

- **Invoice 501 blocks two tickets.** Tickets 101 and 103 both need Bulldog Print Co, so paying the $840 unblocks both.
- **Cash is tight.** $840 + $2,400 = $3,240, leaving $160. The $264 hoodie restock would then push spending to $3,504, which is over the $3,400 balance. The team can't do everything, so Boss and Accounting must prioritize (rent and the overdue invoice come first) and flag the shortfall to the human.
- **Every payment needs human approval.** Agents only prepare payments and purchase orders. The dashboard approves them.

## MCP tools (`mcp_server/server.py`)

All tools read `data/campus_customs_new.db`, return only stored values or arithmetic on them, and return an error instead of guessing when a record is missing.

### 1. `get_stock_and_pricing(sku, size, qty_requested)`
- **Reads:** `inventory`, `pricing`
- **Unlocks:** Ticket 103 (Yale AI Club, 20 × CC-HOOD-NAVY size M at a bulk discount)
- **Why:** In one call it returns the 8 on hand and the shortfall of 12 for the club's 20-hoodie request, plus the $22 unit cost and $58 list price that set the floor for any bulk discount Accounting can approve.

### 2. `get_vendor_invoices(vendor_id)`
- **Reads:** `vendors`, `invoices`, `desk`
- **Unlocks:** Ticket 101 (Tauhid Zaman, 1 × CC-TEE-WHITE size S, which has 0 in stock)
- **Why:** The only way to fill this order is a reprint from Bulldog Print Co (vendor 1). This tool shows that vendor's invoice 501 ($840, 3 days overdue as of desk.date_today) is open, so `can_ship` is false until it's paid, and gives the 5-day lead time to quote the customer.

### 3. `get_lease_and_cash(lease_id)`
- **Reads:** `leases`, `cash_accounts`, `desk`
- **Unlocks:** Ticket 102 (Elm City Properties rent notice, lease 1)
- **Why:** It confirms from the database that lease 1's $2,400 rent is due 2026-09-02 (2 days after desk.date_today) and that $3,400 in checking covers it, leaving $1,000, which is what Facilities and Accounting need before asking a human to approve the payment.

## Agent team (Problem 5)

Code: `backend/agents/` (one module per role plus `team.py`), prompts in `backend/prompts/<agent>.md`, data types in `backend/models.py`. Every agent runs on **`gpt-6-luna` via Portkey** (`PORTKEY_API_KEY`) and gets shop facts **only** from the MCP server above, attached in-process. There is no second data layer. Every agent has an `ask_<other>` tool for each of the other four, so the team is fully connected. Run with `python backend/run_team.py`.

| Agent | Persona | Owns | MCP tools it can call | Returns |
|---|---|---|---|---|
| Boss | The Conductor: air-traffic controller turned retail ops GM | Ticket queue, routing, sign-off | `list_open_tickets`, `get_ticket`, `get_cash_position`, `update_ticket` | `TeamReport` |
| Inventory | The Quartermaster: Toyota Production System and fast-fashion replenishment | Stock by SKU and size, vendors, restock quotes | `get_ticket`, `get_stock_and_pricing`, `list_vendors`, `get_vendor_invoices`, `quote_restock`, `update_ticket` | `SpecialistReport` |
| Accounting | The Controller: Big Four audit partner turned startup CFO | Cash, invoices, discount floor, payment queue | `get_ticket`, `get_cash_position`, `get_vendor_invoices`, `get_stock_and_pricing`, `check_discount`, `quote_restock`, `update_ticket` | `SpecialistReport` |
| Facilities | The Superintendent: New Haven building super and property manager | Lease, rent dates, landlord | `get_ticket`, `get_lease_and_cash`, `get_cash_position`, `update_ticket` | `SpecialistReport` |
| Customer Service | The Concierge: Ritz-Carlton front desk and online-retail support | Every customer-facing draft | `get_ticket`, `get_stock_and_pricing`, `get_vendor_invoices`, `check_discount`, `update_ticket` | `SpecialistReport` |

**When a ticket is resolved** (Boss prompt): every payment it depends on is approved or deliberately deferred for lack of cash, any discount is owner-approved, and Customer Service has a final draft; a vendor delivering an already-paid order doesn't keep it open. The owner signs between runs, so the loop is run → sign → run again, and on a re-run agents read the approval notes instead of re-queuing.

**Agent loop.** Each agent runs Pydantic AI's `agent.iter()` loop: a model request, then tool calls (MCP or `ask_*`), and so on until it returns a structured output. A delegation runs the target agent's own loop inside the caller's tool call and returns its report.

**Audit trail.** `output/audit_trail.json` is a JSON array that is only ever appended to. Each loop step adds one entry with `run_id`, `agent`, `persona`, delegation `chain` (e.g. `boss > inventory`), `depth`, `step`, `kind` (`start`, `model_request`, `model_response`, `final_output`, `error`), and the step detail. That detail is the prompt; the tool calls with arguments; tool results (trimmed to 800 characters); reasoning summaries and text; finish reason; per-response tokens; and cumulative team usage.

## All MCP tools (after Problem 5)

| # | Tool | Tables | Read / write | Added | Used by |
|---|---|---|---|---|---|
| 1 | `get_stock_and_pricing` | `inventory`, `pricing` | read | P3 | Inventory, Accounting, Customer Service |
| 2 | `get_vendor_invoices` | `vendors`, `invoices`, `desk` | read | P3 | Inventory, Accounting, Customer Service |
| 3 | `get_lease_and_cash` | `leases`, `cash_accounts`, `desk` | read | P3 | Facilities |
| 4 | `list_open_tickets` | `tickets`, `desk` | read | P5 | Boss |
| 5 | `get_ticket` | `tickets` | read | P5 | all agents |
| 6 | `get_cash_position` | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | read | P5 | Boss, Accounting, Facilities |
| 7 | `list_vendors` | `vendors`, `invoices` | read | P5 | Inventory |
| 8 | `quote_restock` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | read (quote only) | P5 | Inventory, Accounting |
| 9 | `check_discount` | `pricing` | read | P5 | Accounting, Customer Service |
| 10 | `update_ticket` | `tickets` | **write** (status + appended note) | P5 | all agents |

Why the new tools: `list_open_tickets`/`get_ticket` give Boss the queue and the ids that link tickets to the other tables. `get_cash_position` lines up the overdue $840 invoice and the $2,400 rent against $3,400 in cash in a single call ($160 left). `list_vendors` + `quote_restock` find the right vendor for a shortfall and cost it, e.g. 12 hoodies × $22 = $264 from vendor 1, blocked by invoice 501. `check_discount` tests the Yale AI Club bulk rate against the $22 cost floor. `update_ticket` lets agents record progress on the tickets without changing any other table.

## Safety and guardrails

What a real business would want before agents touch real customers and real money:

- **No agent can move money.** The MCP server has no pay, refund or order tool. Agents only produce `PaymentRequest`s, and a human approves each one on the dashboard's cheque tray, which calls `POST /payments/approve`. That route is the only code path that changes cash. The only write tool is `update_ticket`, which touches only `tickets` and appends to notes rather than overwriting them.
- **Least privilege per role.** Each agent sees a filtered subset of MCP tools (table above). For example, Customer Service can't see cash, and Facilities can't see vendors.
- **Signed writes.** The team layer stamps every `update_ticket` with the agent actually calling it, so one agent can't write a note as another.
- **Facts only from the database.** Prompts forbid invented numbers. Tools return errors, not guesses, for missing rows. Reports carry each number as a `Fact` with its source tool.
- **Money rules in every prompt.** Payments can't exceed cash on hand. Vendors with open invoices don't ship. Discounts never go below unit cost. Customers never see internal finances.
- **Customer protection.** Customer Service only drafts. A human sends. It makes no unapproved discounts and no unconfirmed ship dates, and it shares only the requester's own details.
- **Full audit.** Every loop step, tool call and result is appended to `output/audit_trail.json` with the run id and delegation chain. The file is never wiped, and an unreadable file is set aside rather than overwritten.
- **Reset path.** Agents write only to `data/campus_customs_new.db`. `data/campus_customs.db` stays pristine.

Limits that keep token use in check (set in `backend/agents/team.py`):

- One shared usage counter for the whole run, with `request_limit=60`, `tool_calls_limit=90` and `total_tokens_limit=400,000`. A delegated agent spends from the same budget as Boss.
- `max_tokens=6000` per model response.
- Delegation depth capped at 2 (Boss → specialist → one more specialist), no agent may appear twice in a chain (no ping-pong loops), and at most 12 delegations per run. A refused delegation returns a message instead of an error, so the agent finishes with what it has.
- Prompts tell agents to call each tool once per argument set, bundle related tickets into one ask, and send Accounting one consolidated payment request.
- Tool results logged to the audit file are trimmed to 800 characters.

## Backend routes (Problem 7)

`backend/main.py` (FastAPI). Start from `backend/` with `uvicorn main:app --port 8000` (no `--reload`, so one edit doesn't spawn a second server), which serves `http://localhost:8000` (CORS open to the Vite dev server on `:5173`).

- `GET /tickets`: returns all three tickets with their detailed `status` and a simple `state` of `open` or `resolved`.
- `POST /tickets/{id}/run`: runs the agent team (Boss first, delegating as needed) on that one ticket. It writes Boss's final status for the ticket to the DB (refused as `resolved` while a payment or rate that unblocks it is still unsigned) and returns the `run_id`, the `status` and the `TeamReport`, including the payment queue and rate approvals. Only one run at a time (409 if busy).
- `GET /events?after=N&limit=100&run_id=…`: returns recent audit-trail steps (agent, chain, kind, what it said, tool calls with args, tool results) so the board can poll for new events.
- `POST /payments/approve`: a human approves one queued payment (`kind`, `ref_id`, `payee`, `amount`, `approved_by`). This is the only route that changes cash. It checks the payment against the DB (invoice open and exact amount, rent equals the lease rent, PO vendor has no open invoice, amount ≤ balance), then deducts checking, marks the invoice paid or moves the lease due date forward, writes a `payments` row, notes the linked tickets (and resolves the rent ticket), and appends to the audit trail.
- `POST /pricing/approve`: a human approves a group discount from the team's `rate_approvals` (`ticket_id`, `sku`, `qty`, `discount_pct`, `approved_by`). It checks the SKU and qty against the ticket and refuses a price below `pricing.unit_cost`. It moves no cash; it appends a signed "Approved group rate" note to the ticket, which the team reads on its next run, and adds a `rate_approved` audit entry.
- `GET /cash`: returns the current checking balance from `cash_accounts`.
- `POST /reset`: copies `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run. The audit trail is not wiped; a `reset` entry is appended instead.

## Safety in the backend and dashboard (Problems 7–8)

- **Server-side money checks.** `POST /payments/approve` re-checks every request against the DB, whatever the agent or the browser sent. The invoice must be open and the amount exact. Rent must equal `leases.monthly_rent`. A PO vendor must have no open invoice. The amount must be ≤ the checking balance (409 otherwise). Each approval writes a `payments` row with `approved_by`, plus a `payment_approved` audit entry.
- **A named human signs.** The cheque tray's Approve button and the rate slip's Approve rate button stay disabled until a name is typed in "Signed by". Discounts need the owner's signature just like payments; `POST /pricing/approve` refuses any price below unit cost. Cheques over the balance show "More than checking holds".
- **No premature "resolved".** The backend records Boss's final status but downgrades `resolved` to `awaiting_approval` if the report still has an unsigned payment or rate for that ticket. The board only shows Resolved when the DB does.
- **One run at a time.** An asyncio lock makes a second run or a reset during a run return 409, so two runs never write the same tickets.
- **CORS only for the Vite origin** (`http://localhost:5173`, `http://127.0.0.1:5173`).

## Dashboard (Problem 8)

`frontend/` (React + Vite + TypeScript, `npm run dev` → http://localhost:5173), calls the backend at http://localhost:8000. Design notes: `output/design.md` ("Back-Room Workbench").

| Zone | What it shows | Routes it calls |
|---|---|---|
| Header | Shop date, tickets closed (n / 3), backend status lamp, **Reset shop** (with a confirm) | `GET /tickets`, `POST /reset` |
| Order rail (left) | The three tickets as work-order cards with a **Start the team** button. A card gets the Resolved stamp only when the DB says `resolved` (same as `GET /tickets`), then drops under "Done today". A card with something to sign shows "✎ Needs your signature". | `GET /tickets`, `POST /tickets/{id}/run` |
| Spool (centre) | A roster chip per agent with live status; the live feed (memos, tool calls, delegation slips `Boss → Accounting`, results); then the debrief: decision, customer draft, next steps, deferred items and risks | `GET /events?after=N&run_id=…` (polled) |
| Till (right) | The checking balance (drops only after an approved cheque), a mini ledger of payments, the "Signed by" field, and the tray: cheques from each run's `payment_queue`, plus dashed **rate slips** from `rate_approvals` ("no cash moves") | `GET /cash`, `POST /payments/approve`, `POST /pricing/approve` |

## Full run (Problem 9)

Reset at 2026-10-10 02:06 UTC. Each ticket then went run → sign on the dashboard (signed "Duke Wu") → run again, until `GET /tickets` showed it `resolved`. Results: `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html`, and every step in `output/audit_trail.json`, ending with a `full_run_summary` entry.

| Ticket | Runs | Agents called | Signed | Checking after |
|---|---|---|---|---|
| start | | | | $3,400.00 |
| 101 | `608be2f92767`, `d2852bdfa3ad` | Boss → Inventory, Accounting, Customer Service | invoice 501 $840.00; tee PO $8.00 | $2,552.00 |
| 102 | `09f57b480529` | Boss → Facilities, Accounting | rent $2,400.00 (closes the ticket) | $152.00 |
| 103 | `483b698574a7`, `6fefcf2feed7` | Boss → Inventory, Accounting, Customer Service | 10% group rate ($52.20 × 20); no cash ($264 restock deferred, $112 short) | $152.00 |

The ending $152.00 matches `cash_accounts.checking` in `data/campus_customs_new.db` (3,400 − SUM(payments.amount) 3,248). Facilities was called on 102 only.

An earlier attempt (runs `91201e5d9284`, `0a113bed428d`, `40c0e78b9865`, still in the audit trail) ended with 101 and 103 at `awaiting_approval` in the DB, even though the board stamped them. The fixes were the resolution rule, recording Boss's status in the backend, the rate slip, and a board that reads resolved from the DB.

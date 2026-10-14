# Campus Customs MCP Server

The shared tool layer for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents never query the database directly. They call these tools, which return only data stored in the shop database (plus simple arithmetic on it) and return an error when a record is missing, never a guess.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never touched, so it can be copied back to reset.

**Built with:** [FastMCP](https://gofastmcp.com). Run with `python mcp_server/server.py` (stdio). The agent backend (`backend/agents/team.py`) attaches the same server in-process.

## Tools

| Tool | Inputs | Tables | Returns |
|---|---|---|---|
| `get_stock_and_pricing` | `sku`, `size`, `qty_requested` | `inventory`, `pricing` | Stock on hand, shortfall, unit cost, list price, margin per unit |
| `get_vendor_invoices` | `vendor_id` | `vendors`, `invoices`, `desk` | Vendor specialty and lead days, each invoice with days overdue, open balance, `can_ship` |
| `get_lease_and_cash` | `lease_id` | `leases`, `cash_accounts`, `desk` | Rent, next due date, days until due, cash, whether cash covers rent |
| `list_open_tickets` | none | `tickets`, `desk` | Every unresolved ticket, oldest first, with linked SKU/lease/invoice ids |
| `get_ticket` | `ticket_id` | `tickets` | One ticket with its notes trail |
| `get_cash_position` | `horizon_days` (default 30) | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | Cash vs. open invoices and upcoming rent, most urgent first, with running balance |
| `list_vendors` | none | `vendors`, `invoices` | Each vendor's specialty, lead days, open balance, `can_ship` |
| `quote_restock` | `sku`, `size`, `qty`, `vendor_id` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | Restock cost, arrival date, blocking invoices (a quote only, nothing is ordered) |
| `check_discount` | `sku`, `qty`, `discount_pct` | `pricing` | Discounted price, margin per unit and per order, max discount before selling at cost |
| `update_ticket` | `ticket_id`, `status`, `note`, `agent` | `tickets` (write) | Sets status and appends a dated, signed note |

`update_ticket` is the only tool that writes, and it touches only the `tickets` table. There are no tools that pay, order or change stock. Payments stay with a human.

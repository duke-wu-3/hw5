# Campus Customs Multi-Agent Operations (HW 5)

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the Campus Customs ticket desk. Every agent runs on `gpt-6-luna` through Portkey and gets its facts only from one MCP server over the shop's SQLite database. A FastAPI backend runs the team, and a React board ("Agent Desk") shows the work live. Agents never pay anything: every payment and discount waits for a human signature on the board.

## Layout

| Path | What it is |
|---|---|
| `data/campus_customs.db` | Original database. Never modified; used to reset. |
| `data/campus_customs_new.db` | Working copy. All tools and agents read and write this one. |
| `mcp_server/server.py` | MCP server with the 10 shop tools (see `mcp_server/README.md`). |
| `backend/main.py` | FastAPI routes. |
| `backend/models.py` | Pydantic models shared by the routes and agents. |
| `backend/prompts/*.md` | System prompt for each of the five agents. |
| `backend/agents/` | Agent definitions, tool access per agent, and the team runner. |
| `frontend/` | React + Vite board. |
| `output/` | Write-ups and results from the graded run (see below). |

## Setup (once)

Tested with Python 3.14 and Node 24 (Vite 8 needs Node 20.19+).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your Portkey key in .env
cd frontend && npm install && cd ..
```

The backend loads `PORTKEY_API_KEY` from `.env` (or from your shell if it's already exported).

## Running it

### 1. Copy the original DB to the working copy (clean run)

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The original is never touched, so this always gets you back to the starting state (checking $3,400, tickets 101–103 open).

### 2. Start the MCP server

```bash
python mcp_server/server.py
```

This runs the server over stdio for any MCP client. `.mcp.json` registers it for Claude Code when Claude Code is started in this folder. The FastAPI backend attaches the same server in-process, so you don't need this step just to use the board.

### 3. Start the FastAPI backend

```bash
python -m uvicorn main:app --app-dir backend --port 8000
```

Routes on `http://localhost:8000`:

| Route | Purpose |
|---|---|
| `GET /tickets` | All tickets with status |
| `POST /tickets/{id}/run` | Run the team on one ticket |
| `GET /events` | Live agent activity (also appended to `output/audit_trail.json`) |
| `POST /payments/approve` | Human signs a payment the team prepared |
| `POST /pricing/approve` | Human signs a discount rate |
| `GET /cash` | Current checking balance |
| `POST /reset` | Copy the original DB over the working copy |

### 4. Start the React board

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The board talks to the backend on port 8000.

### 5. Reset the DB before a full three-ticket run

Click **Reset shop** on the board (or `curl -X POST http://localhost:8000/reset`). Then, for each ticket 101, 102 and 103:

1. Select the ticket and click **Start the team**.
2. In the cheque tray, type your name under **Signed by** and sign each payment or rate slip you approve.
3. Click **Start the team** again so Boss confirms the signed items and closes the ticket.

The graded run ended with all three tickets resolved and checking at $152.00 ($3,400 − $840 invoice 501 − $8 tee order − $2,400 rent).

You can also run the team from the command line: `python backend/run_team.py "optional instruction for Boss"`.

## Safety rules

- Agents can't move money. Payments and discounts only happen through the approve routes, with a human name attached.
- `update_ticket` is the only MCP tool that writes, and it only touches the `tickets` table.
- Each agent sees only the tools its role needs (for example, Customer Service can't see cash).
- One model only: `gpt-6-luna` via Portkey.
- The real `.env` is git-ignored; only `.env.example` is committed.

## Outputs

| File | Contents |
|---|---|
| `output/harness.md` | Full write-up: tables, MCP tools, agents, routes, dashboard, safety rules |
| `output/mcp_smoke.json` | Smoke test of every MCP tool |
| `output/desk_tickets.html` | Expected vs. actual per ticket, cash itemization, reflection |
| `output/design.md` | Board design notes |
| `output/resolved_tickets.json` | Final status and outcome per ticket |
| `output/resolved_board.html` | Screenshots of the board for each resolved ticket |
| `output/audit_trail.json` | Every agent step, approval and reset |
| `output/github_url.txt` | This repository's URL |

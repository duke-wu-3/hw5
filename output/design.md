# Campus Customs Agent Desk: Design Notes (Problem 8)

The dashboard lives in `frontend/` (React + Vite + TypeScript). Start it with `npm run dev` from `frontend/`. It opens at http://localhost:5173 and talks to the Problem 7 FastAPI backend at http://localhost:8000. The backend's `CORSMiddleware` allows the `http://localhost:5173` and `http://127.0.0.1:5173` origins.

A designer sub-agent first wrote a visual spec. The build follows it closely. The ideas below are the ones I chose to keep.

## The concept: "The Back-Room Workbench"

Most agent dashboards look like server monitors, with dark panels and log tails. Campus Customs is a small print shop on Chapel Street, so the desk should look like its back counter after closing. The page uses kraft-cream paper, ink-dark text and Yale navy for actions. Work orders are clipped to a rail, the agents talk on a roll of receipt paper, and a chequebook sits within reach. Everything on screen is a physical thing a shop owner already understands: a work order, a memo, a ledger line, a cheque, a rubber stamp. Someone who has never heard of "multi-agent orchestration" can still read the screen.

## Layout: three zones, read left to right

| Zone | What it holds | Why it is there |
|---|---|---|
| **Order rail** (left) | The three tickets (#101, #102, #103) as work-order cards, each with a punched hole and a clip on top. Each card has a **Start the team** button. | This is the input: what needs doing. Open tickets sit on top. Resolved ones drop below a "Done today" divider, so the rail is also a to-do list. |
| **Spool** (centre, widest) | The ticket title, a roster strip with all five agents, the live feed on receipt paper with a torn top edge, and the debrief once the run ends. | This is the work: what the team is doing right now. It gets the most space because it is where you watch. |
| **Till** (right) | The checking balance, a short ledger of recent payments, a signature field and the cheque tray. | This is the money. It stays pinned on screen, so the balance is never more than a glance away. |

Below 1280px the Till becomes a band across the top. Below 1000px everything stacks into one column, the tickets scroll sideways and the balance sticks to the top.

## How the agents read differently

Each agent has its own colour, a monogram avatar and its own kind of paper in the feed. You can tell who is talking without reading the name.

| Agent | Colour | Feed treatment | Why |
|---|---|---|---|
| **Boss** (B) | Yale navy | **Memo slip** with a ruled header and italic serif text | The Boss writes directives, like a manager's memo. |
| **Inventory** (IN) | Pine green | **Stock tag** with a dashed border and a punched tag hole | Inventory thinks in SKUs and sizes, like the swing tags on garments. |
| **Accounting** (AC) | Ledger brown | **Ledger line** on ruled paper with tabular numbers and a double-ruled edge | Accounting cites numbers first, so it should look like a bookkeeper's page. |
| **Facilities** (FA) | Plum | **Work slip** with a coloured clipboard band and a checkbox that ticks when the report is filed | Facilities handles the lease and the building, as a practical to-do list. |
| **Customer Service** (CS) | Teal | **Speech bubble** with rounded corners and a tail | Customer Service is the one agent that talks to people outside the shop. |

Other entries in the feed:
- **Tool calls** are quiet one-line mono rows (`⚙ get_cash_position(horizon_days=30)`) in the agent's colour with a dotted rail. Click one to see the full arguments. They are kept small because they are evidence, not the story.
- **Results coming back** are a single grey line (`↩ Accounting got back get cash position, get ticket`).
- **Delegations** are routing slips: `B ── ▸ AC  Boss → Accounting` with the request quoted underneath, and the arrow draws itself as the slip appears. This shows a manager the routing (who the Boss called and why) instead of hiding it inside the log.
- The **roster strip** above the feed has a chip for each agent with a live dot and a one-line status ("Asking Accounting", "get lease and cash", "Report filed"). You can see who is busy at any moment without scrolling. Agents the Boss never called stay "On shift", which shows that the Boss did not call everyone.

## How a resolved ticket shows up

When the run finishes, the work order gets a red **RESOLVED** rubber stamp with the shop date (`08.31`), not the real date. The stamp has a double border, an ink texture, a −8° tilt and a 280ms press-down animation. The card then moves under "Done today" and the masthead counter goes up ("Closed 1 / 3"). Inside the spool, a **Debrief** appears below the feed:
- **Who did what on this ticket:** one line per agent, taken from that agent's filed report (the Boss's line is the team's run summary). This is the short summary of each agent's work.
- **Decision:** the owner of the ticket and the decision.
- **Reply to the requester:** the draft message as a pull quote, ready to send.
- **Held back / watch out:** deferred work and risks.

A ticket counts as resolved when the database says `resolved` **or** the team has finished a run on it. Payment approvals are a separate human step, so a finished ticket can still show "✎ Needs your signature" on its card. That way the human step stays visible.

## How cash shows up and why it only drops on approval

- The **balance** is the largest number on the page: a serif figure on ledger-ruled card stock, in money green.
- Payments the agents prepared are listed as **"Pending signatures: $X (not deducted)"** in muted text. Agents only *prepare* payments, so the figure does not move until a human signs. The backend enforces this too, because `POST /payments/approve` is the only route that changes cash.
- Each prepared payment shows up as a **cheque** in the tray. It has "Pay to the order of", a boxed amount, the amount written out in words ("Two thousand four hundred and 00/100 dollars"), a memo (invoice / rent / purchase order, the ref #, the tickets it unblocks, the due date) and the agent's reason. A cheque that would overdraw checking is flagged "More than checking holds".
- To approve, you sign your name on the **signature line** in italic serif, which the desk remembers. **Approve & sign** stays disabled until there is a name. This matches the backend's required `approved_by` and makes the approval feel deliberate.
- On approval, the cheque tilts and tears off the pad, and a red `−$2,400.00` chip slides into the till. The balance rolls down to the new figure (650ms ease-out), an ink line sweeps under it, and a new row appears in the mini-ledger. The cheque comes back stamped **PAID #id** in green with your signature on it. With `prefers-reduced-motion`, the figure changes instantly with a highlight instead.

## Small touches that make it a desk you want to sit at

- **Print-shop details:** registration-mark crosshairs in the masthead corners, a tilted "CC" logo block with a gold offset like a misregistered screen print, slightly tilted work orders (±0.4°) that straighten when selected, and a thin "print head" bar that sweeps along a running ticket.
- **Calm live feedback:** a lamp in the masthead (green "Desk open", pulsing amber "Team at work", red "Backend offline — start uvicorn on :8000"), a mono run clock (`0:42`), and typing dots while agents think.
- **Feed that respects the reader:** the spool follows new lines only while you are at the bottom. If you scroll up to read, it stays put and shows a "New lines ↓" pill.
- **Warm copy in the empty states:** "Pick a work order from the rail. The team's waiting by the heat press." (with a line drawing of a tee on a press), "No cheques to sign. Balance is safe — for now.", and once all three are done, "That's a wrap for 08.31. Lock up on your way out."
- **Type:** Fraunces (display and money), Inter Tight (body) and JetBrains Mono (tool calls, ticket numbers, amounts). Every amount uses tabular numbers so digits don't jump while the balance rolls.
- **Accessibility:** all text colours are at least 4.5:1 on the paper, there are visible focus rings, the feed is an `aria-live` log, and motion is reduced when the OS asks for it.
- **Reset shop** (with a confirm prompt) calls `POST /reset` and clears the desk's memory of runs and cheques, ready for a fresh run.

## How the page uses the Problem 7 routes

| Route | Used for |
|---|---|
| `GET /tickets` | The order rail (polled every 5s, and every 1.2s during a run) |
| `POST /tickets/{id}/run` | **Start the team**. The response's `report` feeds the debrief and the cheque tray. |
| `GET /events?after=N` | The live spool: polled every 1.2s during a run, filtered to that run's `run_id` |
| `POST /payments/approve` | **Approve & sign** on a cheque |
| `GET /cash` | The till balance |
| `POST /reset` | **Reset shop** |

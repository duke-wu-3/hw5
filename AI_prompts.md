# AI Prompts Log — Homework 5: Campus Customs Multi-Agent Operations

Log of the prompts I typed to my vibe coder (Claude Code), one section per problem.

## Problem 1: Vibe coder prompts

**Prompt:**
> Create AI_prompts.md at the start of the assignment and keep it updated as I work. This file is the log of what I typed to you (the vibe coder). Put one section for each problem. Each section must include: the problem number and title, at least one prompt I typed, in my own words as much as possible, one follow-up prompt if I needed it (and one sentence on what was lacking after the first).

**Follow-up:** None needed.

## Problem 2: Study the Campus Customs database

**Prompt:**
> Study the Campus Customs database. Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db — later problems update that working copy. Study the three open tickets so you see how they link to other tables. Start output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems.

**Follow-up:** None needed.

## Problem 3: Build the MCP server

**Prompt:**
> Build the MCP server. Write an MCP server in mcp_server using FastMCP. It will talk to data/campus_customs_new.db. You do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server, and you will add more tools to it later. For now, write three tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data; only use information in the database. In output/harness.md, list each of your three MCP tools. For every tool, include which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Vague lines like "reads inventory" score low, so tie the tool to the specific ticket. Also add a short mcp_server/README.md that explains what the MCP server is for, which database file it uses, and the three tools it has.

**Follow-up:** None needed.

## Problem 4: Add the MCP server to the vibe coder and test each tool

**Prompt:**
> Add the MCP server to VibeCoder and test each tool. In your VibeCoder, add your MCP server to this project so the VibeCoder can call the tools. Save the connection JSON text in .mcp.json at the project root. With your VibeCoder connected, test each of your three MCP tools. Save the evidence in output/mcp_smoke.json. For every tool, include the prompt you ask the VibeCoder, the tool name, the tool output, and this output needs to match the values in data/campus_customs_new.db.

**Follow-up:**
> Call each campus-customs MCP tool once (get_stock_and_pricing for CC-HOOD-NAVY size M qty 20, get_vendor_invoices for vendor 1, get_lease_and_cash for lease 1). Save output/mcp_smoke.json with, per tool: the prompt, tool name, arguments, raw tool output, and the matching rows queried directly from data/campus_customs_new.db, plus a match: true/false check.

What was lacking: the first session started at the workspace root, so Claude Code never loaded HW 5/.mcp.json and couldn't call the tools. I reran this in a new session started in HW 5.

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**
> Build the agentic team for Campus Customs using Pydantic AI: Boss, Inventory, Accounting, Facilities and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts, one file per agent, data types in backend/models.py, and the agent files under backend. Use PORTKEY_API_KEY and only gpt-6-luna for every agent. Write each prompt in your own words with the shop rules the agents need; more detailed prompts that cover every part of an agent's work and scope score higher. Add any tools the agents need to the MCP server so they can work the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db; don't invent a second shop tools layer that bypasses MCP. Wire the agents to append to output/audit_trail.json for each agent loop step, with enough to audit later, and never wipe it. In output/harness.md, list each agent and each MCP tool with the tables it uses, plus a short safety section on guardrails and token limits. Update mcp_server/README.md so the tool list matches. When writing the agent prompts, give the agents creative personas, like the "Google engineering master" persona I used in the last homework.

**Follow-up:**
> Have Boss explicitly ask Accounting for a recommended discount rate as a follow-up.

What was lacking: on the first runs the team left the Yale AI Club discount unanswered because the club hadn't named a target rate, so no specific group price was recommended.

## Problem 6: Plan the three tickets

**Prompt:**
> Problem six, plan the three tickets. Before you wire the backend, write down what you expect the team to do on each open ticket. Build output\desk_tickets.html. A page you can double click with one tab per ticket. One hundred one, one hundred two, and one hundred three. Also add empty cache and reflection tabs for later problems. Leave them blank or with a short coming later note for now. On each ticket tab, fill an expected section only. Leave room for an actual section you will fill after you run the agents. For each ticket's expected section, write in your own words who the boss should call first and why, all the agent delegations you expect, not boss calls everyone, and then which MCP tools you expect that run to use. Plans that send every specialist on every ticket score low. You'll compare this plan to what actually happens when your agents resolve the three tickets.

## Problem 7: Backend routes

**Prompt:**
> Problem 7: Backend routes. Our react frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following: return the three tickets and whether each is open or resolved. Take a ticket id and run your agent team on that ticket. Return recent agent events -- what each agent said and which tools they used -- so the board can refresh. Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash). Return the current checking balance from cash_accounts. Reset the database to the original values when you want to try a fresh run. ... from the backend/ folder, start the server with: uvicorn main:app --reload --port 8000 ... This turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what URL / what it does).

## Problem 8: Agent dashboard

**Prompt:**
> For problem eight, agent dashboard, build the front end dashboard in front end backslash with React plus Vite plus TypeScript. The page should call the routes you built in problem seven. At minimum, the board should list all three tickets, let you pick one ticket and start the agent team on it, show each agent and what they are saying slash doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, show the checking balance, it should only drop after an approved pay. Make the dashboard look good. Be creative with the layout and feel. This is a real desk people would want to sit at. So put thought into how it looks. Maybe spin up a sub-agent, um, similar to the other questions. Who is like a professional designer? Um, then tell the front end to talk to your back end. At HTTP uh, localhost 8000. On the back end, allow the Vite page or origin usually that's HTTP localhost 5173 so the browser is allowed to call those routes start the board with npm run dev this opens the react desk in your browser so you can pick tickets and watch agents write output slash design.md with what you chose for the dashboard look layout how agents read differently how resolve tickets and cash show up and why including the creative choices that make it feel special and something humans would actually enjoy using.

## Problem 9: Resolve the tickets

**Prompt:**
> Before testing the agents on a full run over the three tickets, reset the working database, data slash custom, campus customs new.db again, so you start clean. Note the starting checking balance. Then run all three tickets on the board, 101, 102, 103, until each one is resolved. Open output slash desk underscore tickets.html. From problem six, uh, on each ticket tab, fill the actual section from this run. Which agents worked, what they delegated, and which tools they use. Keep your expected section so you can compare the tool. Also, by the way, this is for problem nine. Uh, resolve the tickets. On the cache tab of the same output slash desk underscore tickets.html, itemize the money. Uh, starting checking balance, after the reset for each ticket, how cash changed when the ticket resolved, and why. Which pay slash purchase dollar amount uh, ending checking balance. It must match cash accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. Also save output slash resolved underscore tickets.json for each ticket ID. Final status, short outcome. What each agent contributed, an any human approval. Output slash resolved underscore board.html. A page you can double click with a screenshot of your React board for each resolved ticket. 101, 102, and 103. Append real runs to output slash audit underscore trail.json. Finish output slash harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

**Follow-up:**
> Can you run a retrospective on why things didn't go as planned? I want to make sure I'm getting full credit for this question. So if possible, I'd like you to have things go as per the original prompt.

What was lacking: the first run never got tickets 101 and 103 to `resolved` in the database. The board stamped them resolved just because a run finished. Boss's status rules couldn't close a ticket once payments were signed, Boss skipped `update_ticket`, and the 103 discount had no way to get the owner's approval. So I added a resolution rule, recorded Boss's status in the backend, added a rate-approval slip, and redid the run as run → sign → run again.

## Problem 10: Reflection

**Prompt:**
> can you open the desk_ticket.html file so I can fil the reflection tab? This will be for Problem 10: Reflection.

**Follow-up:**
> the html isn't in a user friendly format. Cna you give me a writeup of the information in the html so I can answer each question? I need to be able to answer: How do you evaluate the performance of the agents on each ticket and why? For each ticket, how did actual compare to the expected plan you wrote earlier? What would have been simpler as one agent with tools and why? Describe three new problems Campus Customs might face that this agent team could solve with the tools you built. Describe three new problems Campus Customs might face that this agent team could not solve with the tools you built and explain the tools and agents you would need to solve them.

> How would I go about answering this? Is there a way for you to show me the information I need to review against here and then I can update it in the thing

> Follow up question on #1: Is 245K input tokens a lot for 71 requests? It sounds like the agents were not working very efficiently on each ticket

> help me answer question #3

> i'm not sure how to answer question #4 or #5 based off what you gave me

> this is what i've written for #1-3, do you mind rephrasing these into my writing style?

> wait i mean can you reword what you said for #4 and #5 into my writing style and provide the output

> Do you mind adding all five of these to the reflection tab?

> yes can you please update it

What was lacking: opening the raw HTML didn't give me the run facts in a form I could answer from, so I needed them organized by question, help reasoning through #1, #3, #4, and #5, and the #4 and #5 ideas reworded in my voice before all five answers (#1–3 in my own wording) went into the Reflection tab, plus two typo fixes in #3.

## Problem 11: Submit to GitHub

**Prompt:**
> Hey for Problem 11: Submit to GitHub. Push your code to a public GitHub repository so graders can clone it. Submit the repo URL to Canvas, and also put it in output/github_url.txt. Do not push my real .env to the GitHub repo. Do include both database files under data/ (the original and your working copy) so graders can run your app easily. This is the expected file layout: *(plus a screenshot of the expected `hw5/` file layout from the assignment)*

**Follow-up:**
> I've already created the repo here is the link https://github.com/duke-wu-3/hw5.git

What was lacking: this Mac had no GitHub login (no gh CLI, SSH key, or saved credentials), so Claude Code couldn't create the repo itself; I created the empty public repo on github.com and gave it the URL to push to.

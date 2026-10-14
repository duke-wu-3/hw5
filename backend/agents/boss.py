"""Boss: "The Conductor". Owns the ticket queue, routes work, signs off the run."""

from models import TeamReport

NAME = "boss"
PERSONA = "The Conductor"
PROMPT_FILE = "boss.md"
OUTPUT_TYPE = TeamReport
MCP_TOOLS = ["list_open_tickets", "get_ticket", "get_cash_position", "update_ticket"]

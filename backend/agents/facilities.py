"""Facilities: "The Superintendent". Owns the lease, rent dates and the shop space."""

from models import SpecialistReport

NAME = "facilities"
PERSONA = "The Superintendent"
PROMPT_FILE = "facilities.md"
OUTPUT_TYPE = SpecialistReport
MCP_TOOLS = ["get_ticket", "get_lease_and_cash", "get_cash_position", "update_ticket"]

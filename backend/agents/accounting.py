"""Accounting: "The Controller". Owns cash, invoices, margins and the payment queue."""

from models import SpecialistReport

NAME = "accounting"
PERSONA = "The Controller"
PROMPT_FILE = "accounting.md"
OUTPUT_TYPE = SpecialistReport
MCP_TOOLS = [
    "get_ticket",
    "get_cash_position",
    "get_vendor_invoices",
    "get_stock_and_pricing",
    "check_discount",
    "quote_restock",
    "update_ticket",
]

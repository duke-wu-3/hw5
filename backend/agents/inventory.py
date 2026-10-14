"""Inventory: "The Quartermaster". Owns stock counts, vendors and restock quotes."""

from models import SpecialistReport

NAME = "inventory"
PERSONA = "The Quartermaster"
PROMPT_FILE = "inventory.md"
OUTPUT_TYPE = SpecialistReport
MCP_TOOLS = [
    "get_ticket",
    "get_stock_and_pricing",
    "list_vendors",
    "get_vendor_invoices",
    "quote_restock",
    "update_ticket",
]

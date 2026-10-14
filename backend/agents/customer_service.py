"""Customer Service: "The Concierge". Owns every word that goes to a customer."""

from models import SpecialistReport

NAME = "customer_service"
PERSONA = "The Concierge"
PROMPT_FILE = "customer_service.md"
OUTPUT_TYPE = SpecialistReport
MCP_TOOLS = [
    "get_ticket",
    "get_stock_and_pricing",
    "get_vendor_invoices",
    "check_discount",
    "update_ticket",
]

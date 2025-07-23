import re
from typing import List, Dict, Optional

def extract_missing_fields(prompt_response: str) -> List[str]:
    """Extract fields that couldn't be determined from the prompt response."""
    missing_fields = []
    if "could not determine" in prompt_response.lower():
        lines = prompt_response.split('\n')
        for line in lines:
            if "could not determine" in line.lower():
                field = line.split("could not determine")[-1].strip().strip(":.").strip()
                if field:  # Only add if we actually found a field name
                    missing_fields.append(field)
    return missing_fields

def generate_prompt_for_missing(field: str) -> str:
    """Generate a user-friendly prompt for a missing field."""
    prompts = {
        "invoice_number": "📋 Please enter the invoice number:",
        "sellers_name": "🏢 Please enter the seller's name:",
        "buyers_name": "👤 Please enter the buyer's name:",
        "date": "📅 Please enter the invoice date (DD/MM/YYYY or DDMMYYYY):",
        "item": "🛍️ Please enter the item name:",
        "quantity": "🔢 Please enter the quantity (numbers only):",
        "amount": "💰 Please enter the amount (numbers only):",
        "payee_name": "👤 Please enter the payee name (who receives the cheque):",
        "senders_name": "👤 Please enter the sender's name (who wrote the cheque):",
        "bank_name": "🏦 Please enter the bank name:",
        "account_number": "🔢 Please enter the account number:"
    }
    return prompts.get(field, f"Please enter the {field.replace('_', ' ')}:")

def validate_field_input(field: str, value: str) -> Optional[str]:
    """Validate user input for specific field types."""
    if field in ["quantity", "amount"]:
        if not value.isdigit():
            return "Please enter a valid number."
    elif field == "date":
        if not re.match(r'^\d{2}[\/-]?\d{2}[\/-]?\d{4}$', value):
            return "Please enter date in DD/MM/YYYY or DDMMYYYY format."
    return None

def update_partial_data(partial_data: str, field: str, value: str) -> str:
    """Update the partial data with user-provided value."""
    # For invoice tuples
    if partial_data.strip().startswith("("):
        return partial_data.replace(f"// Could not determine: {field}", f"'{value}'")
    
    # For SQL queries
    return partial_data.replace(f"// Could not determine: {field}", value)
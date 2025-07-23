import re

def extract_missing_fields(prompt_response: str) -> list:
    """Improved extraction that handles SQL comments better"""
    missing = []
    # Look for both comment styles and field markers
    patterns = [
        r"// Could not determine:?\s*([\w\s]+)",
        r"-- Could not determine:?\s*([\w\s]+)",
        r"/\* Could not determine:?\s*([\w\s]+) \*/"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, prompt_response, re.IGNORECASE)
        missing.extend([m.strip().lower().replace(" ", "_") for m in matches])
    
    return list(set(missing))  # Remove duplicates

def update_partial_data(partial_data: str, field: str, value: str) -> str:
    """More robust partial data updater"""
    field = field.replace(" ", "_")
    
    # For SQL queries
    if "INSERT INTO" in partial_data:
        # Replace comment with value
        pattern = rf"(//|--|/\*)\s*Could not determine:?\s*{field}\s*(\*/)?"
        return re.sub(pattern, f"'{value}'", partial_data, flags=re.IGNORECASE)
    
    # For invoice tuples
    return partial_data.replace(f"// Could not determine: {field}", f"'{value}'")

def validate_field_input(field: str, value: str) -> Optional[str]:
    """Add stricter validation"""
    field = field.lower()
    
    if not value.strip():
        return "Please enter a value."
        
    if field in ["quantity", "amount"]:
        if not value.replace(",", "").isdigit():
            return "Please enter a valid number."
    elif field == "date":
        if not re.match(r'^\d{2}[\/-]?\d{2}[\/-]?\d{4}$', value):
            return "Please enter date in DD/MM/YYYY or DDMMYYYY format."
    elif field in ["senders_name", "payee_name", "bank_name"]:
        if len(value) < 2:
            return "Please enter a valid name."
    
    return None

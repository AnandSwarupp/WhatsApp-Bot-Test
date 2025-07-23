from typing import Dict, Tuple
from missing_data import generate_prompt_for_missing, validate_field_input, update_partial_data

class DataCollectionState:
    """Handles state management for data collection flows."""
    
    @staticmethod
    def handle_invoice_data(sender: str, text: str, current_state: str, partial_data: str) -> Tuple[Dict, str]:
        """
        Handles the invoice data collection state.
        Returns tuple of (response_data, new_state)
        """
        missing_fields = current_state.split(":")[1].split(",")
        current_field = missing_fields[0]
        
        # Validate input using imported function
        error = validate_field_input(current_field, text)
        if error:
            return {"message": error}, current_state
        
        # Update the partial data using imported function
        updated_partial = update_partial_data(partial_data, current_field, text)
        
        if len(missing_fields) > 1:
            # Ask for next missing field
            remaining_fields = missing_fields[1:]
            new_state = f"awaiting_invoice_data:{','.join(remaining_fields)}"
            message = generate_prompt_for_missing(remaining_fields[0])
            return {"message": message, "partial_data": updated_partial}, new_state
        
        # All fields collected - ready to process
        return {"message": "", "complete_data": updated_partial}, "authenticated"

    @staticmethod
    def handle_cheque_data(sender: str, text: str, current_state: str, partial_sql: str) -> Tuple[Dict, str]:
        """
        Handles the cheque data collection state.
        Returns tuple of (response_data, new_state)
        """
        missing_fields = current_state.split(":")[1].split(",")
        current_field = missing_fields[0]
        
        # Validate input using imported function
        error = validate_field_input(current_field, text)
        if error:
            return {"message": error}, current_state
        
        # Update the SQL with user's response using imported function
        updated_sql = update_partial_data(partial_sql, current_field, text)
        
        if len(missing_fields) > 1:
            # Ask for next missing field
            remaining_fields = missing_fields[1:]
            new_state = f"awaiting_cheque_data:{','.join(remaining_fields)}"
            message = generate_prompt_for_missing(remaining_fields[0])
            return {"message": message, "partial_sql": updated_sql}, new_state
        
        # All fields collected - ready to process
        return {"message": "", "complete_sql": updated_sql}, "authenticated"
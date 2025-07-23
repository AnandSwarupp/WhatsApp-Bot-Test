from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests, os, json
from supabase import create_client, Client
from auth import *
from whatsapp import send_button_message
from messenger import send_message
from ocr import ocr_from_bytes
from openai_utils import ask_openai
from datetime import datetime
import re
from missing_data import extract_missing_fields, generate_prompt_for_missing, validate_field_input, update_partial_data
from data_collection_states import DataCollectionState

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ACCESS_TOKEN = "EAAR4EKodEE4BPILOK1gypv8kCNIsAqvHnENsM9K3S70cHyiPtSu8YCB1D0cVtX2BB3ZBC08lUyxaHbDo0abTWgdwZAlwZALtziNuNywE9yq7FjnpxR8J9AJIy8YPlL7i62YwS6DFaoZBxzPJASqJFG8MOIKZAiCmNh5eHXHKrm4nCVi6oIehvXmabJFviudmPHdhZCY24VrY5NE8CCMuVU8wtsMuSG83bnUIEo1kwqF60ctRoZD"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

def format_date(raw_date: str) -> str | None:
    for fmt in ("%d%m%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw_date, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def run_sql_on_supabase(sql_query: str):
    result = supabase.rpc("execute_sql", {"sql": sql_query}).execute()
    return result

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print(json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return {"status": "ok"}

        msg = messages[0]
        sender = msg["from"]
        msg_type = msg["type"]
        state = get_user_state(sender)

        if msg_type == "text":
            text = msg["text"]["body"].strip().lower()
            state = get_user_state(sender)

            if text == "hello":
                send_message(sender, "📧 Please enter your email to begin.")
                set_user_state(sender, "awaiting_email")
                return {"status": "ok"}

            # Handle data collection states first
            if state and state.startswith("awaiting_invoice_data:"):
                response_data, new_state = DataCollectionState.handle_invoice_data(
                    sender, text, state, get_user_intent(sender)
                )
                
                if response_data.get("message"):
                    send_message(sender, response_data["message"])
                
                if new_state != "authenticated":
                    set_user_state(sender, new_state)
                    set_user_intent(sender, response_data.get("partial_data"))
                else:
                    set_user_state(sender, new_state)
                    # Process complete invoice data
                    rows = []
                    for line in response_data["complete_data"].strip().splitlines():
                        line = line.strip().rstrip(',')
                        if line.startswith("(") and line.endswith(")"):
                            parts = [v.strip().strip("'") for v in line[1:-1].split(",")]
                            if len(parts) == 8:
                                rows.append(parts)
                    
                    all_matches = []
                    invoice_details = None
            
                    for row in rows:
                        email, invoice_number, sellers_name, buyers_name, date, item, quantity_str, amount_str = row
                        quantity = int(quantity_str)
                        amount = int(amount_str)

                        if invoice_details is None:
                            invoice_details = {
                                "invoice_number": invoice_number,
                                "sellers_name": sellers_name,
                                "buyers_name": buyers_name,
                                "date": date
                            }
            
                        # Insert into upload_invoice
                        insert_result = supabase.table("upload_invoice").insert({
                            "email": email,
                            "invoice_number": invoice_number,
                            "sellers_name": sellers_name,
                            "buyers_name": buyers_name,
                            "date": date,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        }).execute()
            
                        # Match in tally_invoice
                        match_result = supabase.table("tally_invoice").select("*").match({
                            "invoice_number": invoice_number,
                            "sellers_name": sellers_name,
                            "buyers_name": buyers_name,
                            "date": date,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        }).execute()
            
                        all_matches.append(bool(match_result.data))
            
                    # Send one comprehensive response
                    if invoice_details:
                        match_count = sum(all_matches)
                        total_items = len(all_matches)
                        
                        response = f"""
                    ✅ Invoice {invoice_details['invoice_number']} processed
                     📅 Date: {invoice_details['date']}
                     👤 Seller: {invoice_details['sellers_name']}
                     👥 Buyer: {invoice_details['buyers_name']}
                     📊 Items: {total_items} ({match_count} matched)
                        """
                        send_message(sender, response.strip())
                return {"status": "ok"}

            elif state and state.startswith("awaiting_cheque_data:"):
                response_data, new_state = DataCollectionState.handle_cheque_data(
                    sender, text, state, get_user_intent(sender)
                )
                
                if response_data.get("message"):
                    send_message(sender, response_data["message"])
                
                if new_state != "authenticated":
                    set_user_state(sender, new_state)
                    set_user_intent(sender, response_data.get("partial_sql"))
                else:
                    set_user_state(sender, new_state)
                    try:
                        run_sql_on_supabase(response_data["complete_sql"])

                        # Extract values for matching
                        values_match = re.search(
                            r"VALUES\s*\(['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*(\d+),\s*['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*['\"](.*?)['\"]\)",
                            response_data["complete_sql"],
                            re.IGNORECASE
                        )
                        
                        is_match = False
                        if values_match:
                            payee_name = values_match.group(2)
                            senders_name = values_match.group(3)
                            amount = int(values_match.group(4))
                            date = values_match.group(5)
                            
                            # Check for match in tally_cheque
                            match_result = supabase.table("tally_cheque").select("*").match({
                                "payee_name": payee_name,
                                "senders_name": senders_name,
                                "amount": amount,
                                "date": date
                            }).execute()
                            
                            is_match = bool(match_result.data)
                
                        send_message(sender, "✅ Cheque uploaded successfully.")
                        send_message(sender, f"🧾 Match found : {'Yes' if is_match else 'No'}")
                    except Exception as e:
                        print("❌ Error executing cheque SQL:", e)
                        send_message(sender, "⚠ Failed to process cheque. Please try again.")
                return {"status": "ok"}

            # Original state handling
            if state == "awaiting_email":
                set_user_email(sender, text.lower())
                email = text
                email_text = text

                # Check if user is registered
                result = supabase.table("users").select("email").eq("email", email).execute()
                if result.data:
                    # Registered → ask for OTP
                    generate_and_send_otp(sender, email)
                    set_user_state(sender, "awaiting_otp")
                    send_message(sender, f"📨 OTP sent to {email}. Please reply with the code.")
                else:
                    # Not registered → ask for name
                    set_user_state(sender, "awaiting_name")
                    send_message(sender, "👋 Welcome! Please enter your full name to register.")
                return {"status": "ok"}

            if state == "awaiting_name":
                set_user_intent(sender, text)
                set_user_state(sender, "awaiting_age")
                send_message(sender, "Great. Please enter your age.")
                return {"status": "ok"}

            if state == "awaiting_age":
                try:
                    age = int(text)
                    set_user_otp(sender, str(age))
                    set_user_state(sender, "awaiting_gender")
                    send_message(sender, "👤 Almost done. Enter your gender (e.g., Male/Female/Other).")
                except ValueError:
                    send_message(sender, "❌ Please enter a valid number for age.")
                return {"status": "ok"}

            if state == "awaiting_gender":
                name = get_user_intent(sender)
                age = get_user_otp(sender)
                gender = text.strip()
                email = get_user_email(sender)

                supabase.table("users").insert({
                    "name": name,
                    "age": int(age),
                    "gender": gender,
                    "email": email,
                    "whatsapp": sender
                }).execute()

                # Send OTP
                generate_and_send_otp(sender, email)
                set_user_state(sender, "awaiting_otp")
                send_message(sender, f"✅ You're almost done! OTP sent to {email}. Please reply with the code.")
                return {"status": "ok"}

            if state == "awaiting_otp":
                if text == get_user_otp(sender):
                    mark_authenticated(sender)
                    clear_user(sender)
                    send_message(sender, "✅ OTP verified! You're now logged in.")
                    send_button_message(sender)
                else:
                    send_message(sender, "❌ Incorrect OTP. Try again.")
                return {"status": "ok"}

            if text == "status":
                send_message(sender, f"📌 State: {get_user_state(sender)} | Authenticated: {is_authenticated(sender)}")
                return {"status": "ok"}

            send_message(sender, "👋 Please say 'hello' to get started.")
            return {"status": "ok"}

        if not is_authenticated(sender):
            send_message(sender, "🔒 Please verify by saying 'hello' first.")
            return {"status": "ok"}

        # Button flow
        if msg_type == "interactive":
            button_id = msg["interactive"]["button_reply"]["id"]
            set_user_intent(sender, button_id)

            if button_id == "upload_invoice":
                send_message(sender, "📤 Please upload your invoice.")
            elif button_id == "upload_cheque":
                send_message(sender, "📤 Please upload a scanned cheque.")
            return {"status": "ok"}

        # Media handling
        if msg_type in ["image", "document"]:
            intent = get_user_intent(sender)
            if intent not in ["upload_invoice", "upload_cheque"]:
                send_message(sender, "❗ Please select an option first using the buttons.")
                return {"status": "ok"}

            media_id = msg[msg_type]["id"]
            meta_url = f"https://graph.facebook.com/v19.0/{media_id}"
            meta = requests.get(meta_url, params={"access_token": ACCESS_TOKEN}).json()
            media_url = meta.get("url")

            if not media_url:
                send_message(sender, "⚠️ Failed to get your file. Please try again.")
                return {"status": "ok"}

            try:
                file_bytes = requests.get(media_url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}).content
            except Exception as e:
                print("❌ Error downloading file:", e)
                send_message(sender, "⚠️ Failed to download your file.")
                return {"status": "ok"}

            try:
                ocr_text = ocr_from_bytes(file_bytes)
            except Exception as e:
                print("❌ OCR failed:", e)
                send_message(sender, "❌ OCR failed. Please upload a clear image or PDF.")
                return {"status": "ok"}

            email = get_user_email(sender)

            if intent == "upload_invoice":
                prompt = f"""
                    You are an intelligent invoice parser.
                    
                    From the OCR text below, extract invoice number, seller name, buyer name, date, and each item with quantity & amount.
                    
                    Return only multiple VALUES tuples in this format:
                    (email, invoice_number, sellers_name, buyers_name, date, item, quantity, amount)
                    
                    For example, output exactly like this:
                    ('{email}', 'INV001', 'SellerName', 'BuyerName', '2025-07-18', 'Desk', 10, 10000),
                    ('{email}', 'INV001', 'SellerName', 'BuyerName', '2025-07-18', 'Chair', 5, 5000)
                    
                    ⚠ Include the email as '{email}' in each tuple (taken from the user session).
                    Convert amounts to integers. Format date to YYYY-MM-DD.
                    Do NOT add INSERT INTO statement, comments, explanation, or code blocks — only the raw tuples separated by commas.
                    
                    If any field cannot be determined, add a comment like:
                    // Could not determine: sellers_name
                    // Could not determine: date
                    
                    OCR TEXT:
                    \"\"\"{ocr_text}\"\"\"
                    """
                try:
                    sql_response = ask_openai(prompt)
                    print("OpenAI response:", sql_response)

                    # Check for missing fields
                    missing_fields = extract_missing_fields(sql_response)
                    if missing_fields:
                        set_user_state(sender, f"awaiting_invoice_data:{','.join(missing_fields)}")
                        set_user_intent(sender, sql_response)
                        send_message(sender, generate_prompt_for_missing(missing_fields[0]))
                        return {"status": "ok"}

                    rows = []
                    for line in sql_response.strip().splitlines():
                        line = line.strip().rstrip(',')
                        if line.startswith("(") and line.endswith(")"):
                            parts = [v.strip().strip("'") for v in line[1:-1].split(",")]
                            if len(parts) == 8:
                                rows.append(parts)

                    all_matches = []
                    invoice_details = None
            
                    for row in rows:
                        email, invoice_number, sellers_name, buyers_name, date, item, quantity_str, amount_str = row
                        quantity = int(quantity_str)
                        amount = int(amount_str)

                        if invoice_details is None:
                            invoice_details = {
                                "invoice_number": invoice_number,
                                "sellers_name": sellers_name,
                                "buyers_name": buyers_name,
                                "date": date
                            }
            
                        # Insert into upload_invoice
                        insert_result = supabase.table("upload_invoice").insert({
                            "email": email,
                            "invoice_number": invoice_number,
                            "sellers_name": sellers_name,
                            "buyers_name": buyers_name,
                            "date": date,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        }).execute()
            
                        # Match in tally_invoice
                        match_result = supabase.table("tally_invoice").select("*").match({
                            "invoice_number": invoice_number,
                            "sellers_name": sellers_name,
                            "buyers_name": buyers_name,
                            "date": date,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        }).execute()
            
                        all_matches.append(bool(match_result.data))
            
                    # Send one comprehensive response
                    if invoice_details:
                        match_count = sum(all_matches)
                        total_items = len(all_matches)
                        
                        response = f"""
                    ✅ Invoice {invoice_details['invoice_number']} processed
                     📅 Date: {invoice_details['date']}
                     👤 Seller: {invoice_details['sellers_name']}
                     👥 Buyer: {invoice_details['buyers_name']}
                     📊 Items: {total_items} ({match_count} matched)
                        """
                        send_message(sender, response.strip())
                    else:
                        send_message(sender, "✅ Invoice processed (no items found)")
            
                except Exception as e:
                    print("❌ Error processing invoice:", e)
                    send_message(sender, "⚠ Failed to process invoice. Try again.")


            elif intent == "upload_cheque":
                prompt = f"""
                    You are an intelligent cheque parser.
                    1. Only return the SQL query as plain text without any description, comments, code blocks, or extra characters.
                    2. No use of Markdown or enclosing query in ```sql or ``` blocks.
                    3. Generate the query in a single line or properly formatted with minimal whitespace.
                    4. Ensure the query uses valid SQL syntax that can be executed directly in SQL Server.
                    5.Dont use any /n in the code.
                    6.The name of table is "upload_cheique".
                    
                    Extract the following:
                    - Account Holder Name
                    - Receiver Name
                    - Cheque Date (DDMMYYYY)
                    - Bank Name
                    - Account Number
                    - Amount
                    
                    Return one SQL query like:
                    
                    INSERT INTO upload_cheique (email, payee_name, senders_name, amount, date, bank_name, account_number)
                    VALUES ('{email}', 'Receiver Name', 'Sender Name', 5000, '2025-07-01', 'Bank Name', '1234567890');
                    
                    Convert amount to integer, format date as YYYY-MM-DD.
                    
                    If any field cannot be determined, add a comment like:
                    // Could not determine: senders_name
                    // Could not determine: account_number
                    
                    OCR TEXT:
                    \"\"\"{ocr_text}\"\"\"
                """
            
                try:
                    sql_response = ask_openai(prompt)
                    print("Raw SQL response:", sql_response)  # More descriptive logging
                
                    # Clean and normalize the SQL response
                    sql_response = ' '.join(sql_response.split()).strip()
                    
                    # Debug: Print cleaned SQL for verification
                    print("Cleaned SQL:", sql_response)
                
                    # Check for missing fields with improved extraction
                    missing_fields = extract_missing_fields(sql_response)
                    if missing_fields:
                        print(f"Missing fields detected: {missing_fields}")  # Debug logging
                        
                        # Store the original SQL for reconstruction
                        set_user_state(sender, f"awaiting_cheque_data:{','.join(missing_fields)}")
                        set_user_intent(sender, sql_response)
                        
                        # Get user-friendly field name
                        first_field = missing_fields[0].replace("_", " ")
                        send_message(sender, f"Please enter the {first_field}:")
                        return {"status": "ok"}
                
                    # Execute SQL if no missing fields
                    try:
                        run_sql_on_supabase(sql_response)
                        
                        # Improved regex pattern for value extraction
                        values_pattern = (
                            r"VALUES\s*\([\"']?(.*?)[\"']?\s*,\s*[\"']?(.*?)[\"']?\s*,\s*[\"']?(.*?)[\"']?\s*,"
                            r"\s*(\d+)\s*,\s*[\"']?(.*?)[\"']?\s*,\s*[\"']?(.*?)[\"']?\s*,\s*[\"']?(.*?)[\"']?\s*\)"
                        )
                        values_match = re.search(values_pattern, sql_response, re.IGNORECASE)
                        
                        is_match = False
                        match_details = ""
                        
                        if values_match:
                            payee_name = values_match.group(2).strip("'\"")
                            senders_name = values_match.group(3).strip("'\"")
                            amount = int(values_match.group(4))
                            date = values_match.group(5).strip("'\"")
                            bank_name = values_match.group(6).strip("'\"")
                            account_number = values_match.group(7).strip("'\"")
                
                            # Check for match in tally_cheque
                            match_result = supabase.table("tally_cheque").select("*").match({
                                "payee_name": payee_name,
                                "senders_name": senders_name,
                                "amount": amount,
                                "date": date
                            }).execute()
                            
                            is_match = bool(match_result.data)
                            
                            # Prepare detailed response
                            match_details = (
                                f"🔹 Payee: {payee_name}\n"
                                f"🔹 Sender: {senders_name}\n"
                                f"🔹 Amount: {amount}\n"
                                f"🔹 Date: {date}\n"
                                f"🔹 Bank: {bank_name}\n"
                                f"🔹 Account: {account_number}\n\n"
                                f"🧾 Match Found: {'✅ Yes' if is_match else '❌ No'}"
                            )
                
                        send_message(sender, "✅ Cheque processed successfully!")
                        if match_details:
                            send_message(sender, match_details)
                        else:
                            send_message(sender, "⚠ Could not extract all cheque details for verification")
                
                    except Exception as e:
                        print("❌ Database error:", str(e))
                        send_message(sender, "⚠ Error saving cheque details. Please try again.")
                        return {"status": "ok"}
                
                except Exception as e:
                    print("❌ Cheque processing error:", str(e))
                    error_msg = (
                        "⚠ Failed to process cheque. Please ensure:\n"
                        "1. The image is clear\n"
                        "2. All cheque details are visible\n"
                        "3. Try again with a better photo"
                    )
                    send_message(sender, error_msg)
    except Exception as e:
        print("❌ Unhandled error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"status": "ok"}

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
import ast

app = FastAPI()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ACCESS_TOKEN = "EAAR4EKodEE4BPN46RgFWNYk3ZCJqM3h9EGrYoRlzwWWZAGEhZCaN78G7GSRDoXx83JaqslZCmso7rjM58lyhkjmNBK7ujxXed7tymu7IYipOgWVAijA9fZCLGfPsbaVp9NAFCAtq34vpc4aZC8GK0kDXrABmyZB1MxyZCZBtRA7baBTVoBEPXw7iD0zC59vVImVWYoLanxRQrTRQjfkcFUZBZBjqkzgRfvOzzK03iU6OryGZAvU5ZBogZD"
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
            
            if state == "awaiting_invoice_details":
                partial = get_user_partial_invoice(sender)
                
                # Ask in sequence: invoice_number → seller → buyer → date
                if not partial.get("invoice_number"):
                    partial["invoice_number"] = text
                    set_user_partial_invoice(sender, partial)
                    send_message(sender, "👤 Enter seller's name:")
                    return {"status": "ok"}

                if not partial.get("sellers_name"):
                    partial["sellers_name"] = text
                    set_user_partial_invoice(sender, partial)
                    send_message(sender, "👥 Enter buyer's name:")
                    return {"status": "ok"}

                if not partial.get("buyers_name"):
                    partial["buyers_name"] = text
                    set_user_partial_invoice(sender, partial)
                    send_message(sender, "📅 Enter date (DDMMYYYY or DD/MM/YYYY):")
                    return {"status": "ok"}

                if not partial.get("date"):
                    date_str = format_date(text)
                    if not date_str:
                        send_message(sender, "❌ Invalid date format. Please try again (DDMMYYYY or DD/MM/YYYY).")
                        return {"status": "ok"}
                    partial["date"] = date_str
                    set_user_partial_invoice(sender, partial)

                    # Finalize invoice upload (save placeholder item)
                    supabase.table("upload_invoice").insert({
                        "email": partial["email"],
                        "invoice_number": partial["invoice_number"],
                        "sellers_name": partial["sellers_name"],
                        "buyers_name": partial["buyers_name"],
                        "date": partial["date"],
                        "item": "MANUAL_ENTRY",
                        "quantity": 1,
                        "amount": 0
                    }).execute()

                    clear_user_partial_invoice(sender)
                    set_user_state(sender, "authenticated")
                    send_message(sender, "✅ Invoice data completed manually and uploaded.")
                    return {"status": "ok"}


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
                send_message(sender, "🎂 Great. Please enter your age.")
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

                # Now send OTP after registration
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
            
            elif state == "awaiting_missing_invoice_fields":
                session_data = get_user_session(sender)
                pending_rows = session_data.get("pending_rows", [])
                completed_rows = session_data.get("completed_rows", [])
                all_matches = session_data.get("all_matches", [])
            
                if not pending_rows:
                    send_message(sender, "✅ All rows completed.")
                    return {"status": "ok"}
            
                current_row_data = pending_rows[0]
                row = list(current_row_data["row"])
                missing_fields = current_row_data["missing_fields"]
            
                current_field = list(missing_fields.keys())[0]
                row_idx = ["email", "invoice_number", "sellers_name", "buyers_name", "date", "item", "quantity", "amount"].index(current_field)
            
                # Update the field with the user's message
                if current_field == "date":
                    formatted = format_date(message_text)
                    if not formatted:
                        send_message(sender, "❌ Invalid date format. Use DD/MM/YYYY or DDMMYYYY.")
                        return {"status": "ok"}
                    row[row_idx] = formatted
                elif current_field in ["quantity", "amount"]:
                    try:
                        row[row_idx] = int(message_text.strip())
                    except ValueError:
                        send_message(sender, f"❌ Please enter a valid number for {current_field}.")
                        return {"status": "ok"}
                else:
                    row[row_idx] = message_text.strip()
            
                del missing_fields[current_field]
            
                if missing_fields:
                    # Still more fields to fill
                    current_row_data["row"] = tuple(row)
                    set_user_session(sender, {
                        "pending_rows": pending_rows,
                        "completed_rows": completed_rows,
                        "all_matches": all_matches
                    })
                    next_field = list(missing_fields.keys())[0]
                    send_message(sender, f"📌 Enter value for '{next_field}':")
                    return {"status": "ok"}
                else:
                    # Row is now complete — insert and match
                    pending_rows.pop(0)
                    completed_rows.append(tuple(row))
                    email, invoice_number, sellers_name, buyers_name, date, item, quantity, amount = row
            
                    # Insert into Supabase
                    supabase.table("upload_invoice").insert({
                        "email": email,
                        "invoice_number": invoice_number,
                        "sellers_name": sellers_name,
                        "buyers_name": buyers_name,
                        "date": date,
                        "item": item,
                        "quantity": quantity,
                        "amount": amount
                    }).execute()
            
                    # Match against tally_invoice
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
            
                    # Save updated session
                    set_user_session(sender, {
                        "pending_rows": pending_rows,
                        "completed_rows": completed_rows,
                        "all_matches": all_matches
                    })
            
                    if pending_rows:
                        next_missing = list(pending_rows[0]["missing_fields"].keys())[0]
                        send_message(sender, f"📌 Next row — enter value for '{next_missing}':")
                        return {"status": "ok"}
                    else:
                        match_count = sum(all_matches)
                        total_items = len(completed_rows)
            
                        invoice_number = completed_rows[0][1]
                        date = completed_rows[0][4]
                        sellers_name = completed_rows[0][2]
                        buyers_name = completed_rows[0][3]
            
                        summary = f"""
            ✅ Invoice {invoice_number} processed
            📅 Date: {date}
            👤 Seller: {sellers_name}
            👥 Buyer: {buyers_name}
            📊 Items: {total_items} ({match_count} matched)
                        """
                        send_message(sender, summary.strip())
                        set_user_state(sender, None)
                        clear_user_session(sender)
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
            
                ⚠ Include the email as '{email}' in each tuple.
                Format the date as YYYY-MM-DD. Convert amounts to integers.
                Do NOT add explanations — only raw Python tuples, comma-separated.
            
                OCR TEXT:
                \"\"\"{ocr_text}\"\"\"
                """
            
                try:
                    sql_response = ask_openai(prompt)
                    print("OpenAI response:", sql_response)
            
                    rows = []
                    for line in sql_response.strip().splitlines():
                        line = line.strip().rstrip(',')
                        if line.startswith("(") and line.endswith(")"):
                            try:
                                row = ast.literal_eval(line)
                                if len(row) == 8:
                                    rows.append(row)
                            except Exception as e:
                                print("⚠ Failed to parse line:", line, e)
            
                    if not rows:
                        send_message(sender, "⚠️ Could not extract any valid invoice items. Please try again or upload a clearer image.")
                        return {"status": "ok"}
            
                    incomplete_rows = []
                    complete_rows = []
            
                    for row in rows:
                        email, invoice_number, sellers_name, buyers_name, date, item, quantity, amount = row
                        missing = {}
            
                        if not invoice_number: missing["invoice_number"] = ""
                        if not sellers_name: missing["sellers_name"] = ""
                        if not buyers_name: missing["buyers_name"] = ""
                        if not date: missing["date"] = ""
                        if not item: missing["item"] = ""
                        if not quantity: missing["quantity"] = ""
                        if not amount: missing["amount"] = ""
            
                        if missing:
                            incomplete_rows.append({
                                "row": row,
                                "missing_fields": missing
                            })
                        else:
                            complete_rows.append(row)
            
                    # Upload complete rows
                    for row in complete_rows:
                        email, invoice_number, sellers_name, buyers_name, date, item, quantity, amount = row
                        supabase.table("upload_invoice").insert({
                            "email": email,
                            "invoice_number": invoice_number,
                            "sellers_name": sellers_name,
                            "buyers_name": buyers_name,
                            "date": date,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        }).execute()
            
                    # Handle incomplete rows
                    if incomplete_rows:
                        set_user_state(sender, "awaiting_missing_invoice_fields")
                        set_user_session(sender, {
                            "pending_rows": incomplete_rows,
                            "completed_rows": complete_rows
                        })
                        first = incomplete_rows[0]
                        field = list(first["missing_fields"].keys())[0]
                        send_message(sender, f"⚠️ Some details are missing. Please enter the value for '{field}':")
                        return {"status": "ok"}
            
                    send_message(sender, f"✅ Uploaded {len(complete_rows)} invoice items.")
                    return {"status": "ok"}
            
                except Exception as e:
                    print("❌ Error:", e)
                    send_message(sender, "⚠ Something went wrong while processing your invoice.")


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
                    
                    OCR TEXT:
                    \"\"\"{ocr_text}\"\"\"
                """
            
                try:
                    sql_response = ask_openai(prompt)
                    print("SQL to execute:", sql_response)
                    
                    # Execute the SQL first
                    run_sql_on_supabase(sql_response)
                    
                    # Now parse values for matching (simplified approach)
                    # Extract values from SQL string (this is a basic example - improve as needed)
                    values_match = re.search(
                        r"VALUES\s*\(['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*(\d+),\s*['\"](.*?)['\"],\s*['\"](.*?)['\"],\s*['\"](.*?)['\"]\)",
                        sql_response,
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
                    print("❌ Error during cheque processing:", e)
                    send_message(sender, "⚠ Failed to process cheque. Please try again with a clearer image.")

    except Exception as e:
        print("❌ Unhandled error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"status": "ok"}

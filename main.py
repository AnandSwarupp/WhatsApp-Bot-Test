from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests, os, json

from auth import (
    get_user_state,
    set_user_state,
    get_user_email,
    set_user_email,
    get_user_otp,
    set_user_otp,
    generate_and_send_otp,
    is_authenticated,
    mark_authenticated,
    clear_user,
    set_user_intent,
    get_user_intent
)

from whatsapp import send_message, send_button_message
from ocr import ocr_from_bytes
from openai_utils import ask_openai

app = FastAPI()

ACCESS_TOKEN = "EAAR4EKodEE4BPOCnLiAIFqPNHBXD4BSnNcj2Ns6kRAqAIhEooAU42daPGAX5QS8hz6hlQui6Wgw7zqPwYRHfaHKLE6eMH0x6U8S4ZA8jDhSliT6oC06oH52xivRZClIIEplj81IDn5OWQr3zb2gmykcFrTRAZB9haYL5ZCZAioIObvzM8XZCgOBkHAH7vrlpc1bL11I0IP2tfEqef96KvvPniViVnRixcudeD0WbEMf0Q7ph0ZD"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

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

        # OTP verification and authentication
        if msg_type == "text":
            text = msg["text"]["body"]
            state = get_user_state(sender)

            if state == "awaiting_otp":
                if text == get_user_otp(sender):
                    clear_user(sender)
                    mark_authenticated(sender)
                    send_message(sender, "✅ OTP verified!")
                    send_button_message(sender)
                else:
                    send_message(sender, "❌ Incorrect OTP. Try again.")
                return {"status": "ok"}

            elif text.lower() == "hello":
                send_message(sender, "📧 Please enter your email for verification.")
                set_user_state(sender, "awaiting_email")
                return {"status": "ok"}

            elif state == "awaiting_email":
                generate_and_send_otp(sender, text)
                send_message(sender, f"📨 OTP sent to {text}. Please reply with the code.")
                return {"status": "ok"}

            elif text.lower() == "status":
                send_message(sender, f"📌 State: {get_user_state(sender)} | Auth: {is_authenticated(sender)}")
                return {"status": "ok"}

        # Block unauthenticated users
        if not is_authenticated(sender):
            send_message(sender, "🔒 Please verify by saying 'hello' first.")
            return {"status": "ok"}

        # Handle button clicks
        if msg_type == "interactive":
            button_id = msg["interactive"]["button_reply"]["id"]
            set_user_intent(sender, button_id)

            if button_id == "upload_invoice":
                send_message(sender, "📤 Please upload your invoice (PDF or image).")
            elif button_id == "upload_cheque":
                send_message(sender, "📤 Please upload a scanned cheque.")
            return {"status": "ok"}

        # Handle file uploads
        if msg_type in ["image", "document"]:
            intent = get_user_intent(sender)
            if intent not in ["upload_invoice", "upload_cheque"]:
                send_message(sender, "❗ Please select an option first using the buttons.")
                return {"status": "ok"}

            media_id = msg[msg_type]["id"]
            print(f"📎 Media ID: {media_id}")

            # Get media URL
            meta_url = f"https://graph.facebook.com/v19.0/{media_id}"
            meta = requests.get(meta_url, params={"access_token": ACCESS_TOKEN}).json()
            media_url = meta.get("url")
            print(f"📥 Media URL: {media_url}")

            # Download file
            file_bytes = requests.get(media_url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}).content
            print(f"📂 File size: {len(file_bytes)} bytes")

            # OCR processing
            try:
                ocr_text = ocr_from_bytes(file_bytes)
                print(f"📄 OCR Text:\n{ocr_text}")
            except Exception as e:
                print("❌ OCR Error:", e)
                send_message(sender, "❌ OCR failed. Please upload a clear image or PDF.")
                return {"status": "ok"}

            if intent == "upload_invoice":
                prompt = f"""
                    You are an intelligent OCR post-processor for invoices.

                    Extract the following fields clearly from the raw OCR text below:
                    - Invoice Number
                    - Seller Name
                    - Buyer Name
                    - Invoice Date
                    - Item(s)
                    - Quantity
                    - Amount (Total)

                    If any field is missing or unclear, write "Not Found".

                    OCR Text:
                    \"\"\"
                    {ocr_text}
                    \"\"\"

                    Return the output in this format:
                    Invoice Number: ...
                    Seller Name: ...
                    Buyer Name: ...
                    Invoice Date: ...
                    Items:
                    - Item: ...
                        Quantity: ...
                        Amount: ...
                    Total Amount: ...
                    """
            elif intent == "upload_cheque":
                prompt = prompt = f"""
                    You are an intelligent OCR post-processor for bank cheques.

                    Extract the following details from the OCR text of a cheque:
                    - Account Holder Name (Give the signing authority name.)
                    - Receiver Name (the person being paid, appears after the word "Pay")
                    - Cheque Date
                    - Bank Name
                    - Cheque Number
                    - Amount (in numbers or words)

                    If a field is missing, write "Not Found".

                    OCR Text:
                    \"\"\"
                    {ocr_text}
                    \"\"\"

                    Return the result in this format:
                    Account Holder Name: ...
                    Receiver Name: ...
                    Cheque Date: ...
                    Bank Name: ...
                    Cheque Number: ...
                    Amount: ...
                    """
            
            else:
                print("No valid field found!!!")
                
            # OpenAI call
            try:
                response_text = ask_openai(prompt)
                print(f"🤖 OpenAI Raw Response:\n{response_text}")
            
                # Manual parsing (fallback if JSON not returned)
                parsed = {}
                for line in response_text.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        parsed[key.strip().lower().replace(" ", "_")] = value.strip()
            
            except Exception as e:
                print("❌ OpenAI error:", e)
                send_message(sender, "⚠️ Failed to understand the document. Try again.")
                return {"status": "ok"}


            # Send formatted message
            if intent == "upload_invoice":
                reply = response_text
            else:
                reply = response_text
                
            send_message(sender, reply)
            return {"status": "ok"}

    except Exception as e:
        print("Unhandled error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"status": "ok"}

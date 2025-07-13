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

ACCESS_TOKEN = "EAAR4EKodEE4BPEcUjEYqeK9w5C6bY8TT4RHZAS5DPTuFbEtpZBiE0zZCxwVIwNeHShjIqwqzOcKQe7CGv80dJNUGo86nrO7pZBeNqgksVYqBbmamMtvtbJUwGZBHpajAkDCWEx4HcT8wfyexWfzM11e0C8oorpriQQVtPzefp2cXpF14ag55flZCRb8egpMeP3V5ZAd24ZCuegbmWKnZCZCIaVZCQHrTK1HEl9PyVaUdu6bGIQe0QZDZD"
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

        # OTP verification
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
                from auth import generate_and_send_otp
                generate_and_send_otp(sender, text)
                send_message(sender, f"📨 OTP sent to {text}. Please reply with the code.")
                return {"status": "ok"}

            elif text.lower() == "status":
                from auth import get_user_state, is_authenticated
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

        # Handle file upload
        if msg_type in ["image", "document"]:
            intent = get_user_intent(sender)
            if intent not in ["upload_invoice", "upload_cheque"]:
                send_message(sender, "❗ Please select an option first using the buttons.")
                return {"status": "ok"}

            media_id = msg[msg_type]["id"]

            # Get media URL
            url = f"https://graph.facebook.com/v19.0/{media_id}"
            meta = requests.get(url, params={"access_token": ACCESS_TOKEN}).json()
            media_url = meta["url"]

            # Download file
            file_bytes = requests.get(media_url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}).content

            # OCR processing
            ocr_text = ocr_from_bytes(file_bytes)
            if ocr_text.startswith("❌"):
                send_message(sender, ocr_text)
                return {"status": "ok"}

            # Prompt setup
            if intent == "upload_invoice":
                prompt = f"Extract invoice number, customer name, and amount from this:\n{ocr_text}"
            else:
                prompt = f"Extract account holder, receiver, and amount from this cheque text:\n{ocr_text}"

            # OpenAI call
            try:
                response_text = ask_openai(prompt)
                parsed = json.loads(response_text)
            except Exception as e:
                print("❌ OpenAI error:", e)
                send_message(sender, "⚠️ Failed to understand the document. Try again.")
                return {"status": "ok"}

            # Send formatted message
            if intent == "upload_invoice":
                reply = f"""🧾 Invoice Parsed:
                Customer Name: {parsed.get("customer_name")}
                Invoice Number: {parsed.get("invoice_number")}
                Amount: ₹{parsed.get("amount")}"""
            else:
                reply = f"""🏦 Cheque Parsed:
                Account Holder: {parsed.get("account_holder")}
                Receiver: {parsed.get("receiver")}
                Amount: ₹{parsed.get("amount")}"""

            send_message(sender, reply)
            return {"status": "ok"}

    except Exception as e:
        print("Unhandled error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"status": "ok"}

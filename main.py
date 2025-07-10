from fastapi import FastAPI, Request
import requests
import json
import os
from fastapi.responses import PlainTextResponse
from collections import defaultdict
import random
from auth import (
    get_user_state, set_user_state, set_user_email, get_user_email,
    generate_and_send_otp, get_user_otp, clear_user,
    set_user_intent, get_user_intent
)
from whatsapp import send_message, send_button_message, handle_button_click
from ocr import ocr_from_bytes



app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = "EAAR4EKodEE4BPFB9GZBXxJ62mjyz5BZChaRdY9ZAKSR8ttxwerG8Podj5VxsGDyPa33s804KPilAAUPmCLZBih6oCjdFtIvzZBh4DX9AAPROtMfkRlffIQ53Qht2HQUgC9fmAgfooWK7jbXGTuG0Uke1rZBxAOx3dRfLCQgYZBhPB5ZAzdptNQtIa653KFV4YcZBReXwigUPBTF1lsBwNi16ojzZCZCIrPt5PVpxZBbFYgxuJ3Ig0dIZD"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GRAPH_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

user_intent = defaultdict(lambda: "unknown")



@app.get("/webhook")
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return PlainTextResponse("Invalid verification", status_code=403)

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    print(json.dumps(body, indent=2))


    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")

        if messages:
            msg = messages[0]
            sender = msg["from"]
            msg_type = msg["type"]
            text = msg["text"]["body"].strip() if msg_type == "text" else ""

            if msg_type == "text":
                text = msg["text"]["body"].strip()

                if text.lower() == "hello":
                    set_user_state(sender, "awaiting_email")
                    send_message(sender, "👋 Please enter your email to receive an OTP for verification.")

                elif get_user_state(sender) == "awaiting_email":
                    if "@" in text and "." in text:
                        set_user_email(sender, text)
                        generate_and_send_otp(sender, text)
                        send_message(sender, "📧 OTP has been sent to your email. Please enter it here.")
                    else:
                        send_message(sender, "❌ Invalid email. Please try again.")

                elif get_user_state(sender) == "awaiting_otp":
                    if text == get_user_otp(sender):
                        clear_user(sender)
                        send_message(sender, "✅ OTP verified!")
                        send_button_message(sender)
                    else:
                        send_message(sender, "❌ Incorrect OTP. Try again.")

                else:
                    send_message(sender, f"You said: {text}")

            elif msg_type == "interactive":
                button_id = msg["interactive"]["button_reply"]["id"]
                user_intent[sender] = button_id 
                handle_button_click(sender, button_id)

            elif msg_type in ["image", "document"]:
                    try:
                        doc_type = get_user_intent(sender)
                    
                        media_id = msg[msg_type]["id"]
                        media_metadata_url = f"https://graph.facebook.com/v19.0/{media_id}"
                        media_metadata_response = requests.get(media_metadata_url, params={"access_token": "EAAR4EKodEE4BPFB9GZBXxJ62mjyz5BZChaRdY9ZAKSR8ttxwerG8Podj5VxsGDyPa33s804KPilAAUPmCLZBih6oCjdFtIvzZBh4DX9AAPROtMfkRlffIQ53Qht2HQUgC9fmAgfooWK7jbXGTuG0Uke1rZBxAOx3dRfLCQgYZBhPB5ZAzdptNQtIa653KFV4YcZBReXwigUPBTF1lsBwNi16ojzZCZCIrPt5PVpxZBbFYgxuJ3Ig0dIZD"})
                        media_url = media_metadata_response.json().get("url")

                        media_data_response = requests.get(media_url, headers=headers)
                        file_bytes = media_data_response.content

                        extracted_text = ocr_from_bytes(file_bytes)

                    except Exception as e:
                        print("OCR processing error:", e)
                        send_message(sender, "⚠️ There was an error processing your document. Please try again.")


    except Exception as e:
        print("Webhook Error:", e)

    return {"status": "ok"}

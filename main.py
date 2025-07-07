from fastapi import FastAPI, Request
import requests
import json
import os
from fastapi.responses import PlainTextResponse
from collections import defaultdict

app = FastAPI()

VERIFY_TOKEN = "1234567890"
ACCESS_TOKEN = "EAAR4EKodEE4BPAMQQMuq3XzuP9y0yZBPMjmm3QpNlqwBtQtkOnuIM520SzdI32JZB2m6S4mKFkDSyb5vHQ4VPc8xRtBg21WVyHQpOA1RzXQ45a9ijeOC9RZAP7czrZB0keuaFSAE9mHhxh0k9egimQ9qQQ1plf8N9b3JtVKw746r5qYWAEXPOye8vuoy1Pjj"
PHONE_NUMBER_ID = "718433208015957"
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

            if msg_type == "text":
                text = msg["text"]["body"].lower()
                if "hello" in text:
                    send_button_message(sender)
                else:
                    send_message(sender, f"You said: {text}")

            elif msg_type == "interactive":
                button_id = msg["interactive"]["button_reply"]["id"]
                handle_button_click(sender, button_id)

            elif msg_type in ["image", "document"]:
                    doc_type = user_intent.get(sender, "unknown")
                    send_message(sender, f"Thanks! We received your {doc_type}. We'll process it shortly.")

    except Exception as e:
        print("Webhook Error:", e)

    return {"status": "ok"}

def send_message(to: str, message: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(GRAPH_API_URL, headers=headers, json=payload)
    print(response.json())

def send_button_message(to: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Welcome to FinBot! What would you like to do?"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "upload_cheque",
                            "title": "📓 Upload Cheque"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "upload_invoice",
                            "title": "💼 Upload Invoice"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "chat_finance",
                            "title": "💬 Chat"
                        }
                    }
                ]
            }
        }
    }
    response = requests.post(GRAPH_API_URL, headers=headers, json=payload)
    print(response.json())

def handle_button_click(to: str, button_id: str):
    if button_id.startswith("upload_"):
        doc_type = button_id.replace("upload_", "")
        user_intent[to] = doc_type
        send_message(to, f"Please upload your {doc_type} now.")
    elif button_id == "chat_finance":
        send_message(to, "Great! Ask me any financial question, and I’ll help you.")
    else:
        send_message(to, "Invalid choice. Please try again.")

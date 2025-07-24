import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPJilqEX3v9DqvJZCmZAqebsamUXQKP2KY6RjWqEY0NeRdXiUoSD4QhCuJW3lkGNTBVy2K9HzMaZBPu0eveMyxsiq7j6ZBLCdlDsYntiHMtR8oBCVqrDBK8oJpB97fwEaJrxeY5ynZAR5DdjdUAZCxqAj5cBCyVEJyr6W9LiBrS37rydYRUgTs0PVJsZC0HIz2ipZApyErFtSqZBNZBurut7nLr66uFMoMZAGih6IAZDZD"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GRAPH_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def send_message(to: str, message: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(GRAPH_API_URL, headers=headers, json=payload)
    print(response.json())

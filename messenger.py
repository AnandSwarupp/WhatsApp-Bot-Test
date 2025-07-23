import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPCNvY3oM7IEGyAtUx4TGi8zSVdC3jqRFZAEEZChNxtrBtEvLRqx1fpgyPS0b5KQlHmVNJXjtthV8E60BUpQLrAhyZCk9X6wjOjJJGlyhUdprAW8Rp7d9Uqd0IZBvDeb6jU1BNMhfnJK52PNg9XZC92hPA2ho4eLV5T9z6UnZCjQ7Fd9QS1d9wgLvhc6PB90fXRpLZCldhgzYpwIopAnZBHRUdW5NJxaZC6ZAGZB1gZDZD"
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

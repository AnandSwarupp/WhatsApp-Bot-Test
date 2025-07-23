import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPGAnZBA60Gz4sEAPZBt0FatiyjxQ1YDDr22I1HwKGePaWQmLGE6kyl4tZAxd9rMfEn4hV9VSsZBZCDnmzRjTZC9hP0u5eeMNZCSgRi05pd0cll7ZCZBZBlBDtYE2Bw0ahwjqYF8zX64GIGJB829ZBmaIBNKSln7AZBEpH2cf9YEzGYKQdDS6ynzONSsezZCcgxqrG889vfGBrVJSa1xkOC1LmZA6VqNDlo4dqgDUZCwAAZDZD"
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

import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPN46RgFWNYk3ZCJqM3h9EGrYoRlzwWWZAGEhZCaN78G7GSRDoXx83JaqslZCmso7rjM58lyhkjmNBK7ujxXed7tymu7IYipOgWVAijA9fZCLGfPsbaVp9NAFCAtq34vpc4aZC8GK0kDXrABmyZB1MxyZCZBtRA7baBTVoBEPXw7iD0zC59vVImVWYoLanxRQrTRQjfkcFUZBZBjqkzgRfvOzzK03iU6OryGZAvU5ZBogZD"
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

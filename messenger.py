import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPILOK1gypv8kCNIsAqvHnENsM9K3S70cHyiPtSu8YCB1D0cVtX2BB3ZBC08lUyxaHbDo0abTWgdwZAlwZALtziNuNywE9yq7FjnpxR8J9AJIy8YPlL7i62YwS6DFaoZBxzPJASqJFG8MOIKZAiCmNh5eHXHKrm4nCVi6oIehvXmabJFviudmPHdhZCY24VrY5NE8CCMuVU8wtsMuSG83bnUIEo1kwqF60ctRoZD"
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

import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPKHWndhmGeK2ZAeC734XQsP92J8y0aTs6RBzOTPnqXKxOQN9YZCUgtFFVTYe9oZCR9ZBILx8ZBnMRvZB8HjvY80xoKdmhUBcuAUYZBYYHdy5yrEljkrkkw528c31FVNHwII8TMZBq80bpR4EF6SZBF0h8vlA0OMLHtFHpMuPcE6dZCSaDHwrGZCm1Bzt2TMTuhDOEzsh07bcCRxV785xOXqZCCttE6HvzWDyMBbL4YcZD"
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

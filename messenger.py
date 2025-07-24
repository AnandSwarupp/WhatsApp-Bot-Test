import requests
import os

ACCESS_TOKEN = "EAAR4EKodEE4BPOy0KihfAlMe3pEnYnjcDT7SW8kn2Wc7l2VA09ylsLIRm4gjNVQPHdwhQZAF9R7eaJZAcI6dH09JSZCR1kKobTV74fdD357ayMOjgstssmlG3ZBbCZBAeY9EkyYIy2ZB80ZBCDB9WWQW42MHco5tii5UmSZAfvSpv1GXuI7Lu8sZAZCZAvHJxosVZA8bspisTgHsz1ZAingWzQcEQ5RkRPUXaNhrbqQhTlt2cNiUrrGMZD"
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

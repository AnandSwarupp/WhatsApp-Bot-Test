import os
import requests

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")

def ask_openai(prompt: str) -> str:
    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT_NAME}/chat/completions?api-version={AZURE_API_VERSION}"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_KEY
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are an invoice or cheque parser."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 500
    }

    try:
        print("try block started")
        response = requests.post(url, headers=headers, json=payload)
        print(response.status_code, response.text)
    
        response.raise_for_status()
    
        try:
            result = response.json()
            print("✅ OpenAI Result:", result)
            return result["choices"][0]["message"]["content"]
        except ValueError as json_err:
            print("❌ JSON Decode Error:", json_err)
            return "❌ Failed to parse OpenAI response."
    
    except requests.exceptions.RequestException as e:
        print("❌ OpenAI error:", e)
        return f"❌ OpenAI error: {e}"


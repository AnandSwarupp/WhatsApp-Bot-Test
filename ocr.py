import os
import requests

AZURE_OCR_URL = os.getenv("AZURE_OCR_URL") 
AZURE_KEY = os.getenv("AZURE_KEY")

def ocr_from_bytes(file_bytes: bytes):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }

    response = requests.post(AZURE_OCR_URL, headers=headers, data=file_bytes)
    
    if response.status_code != 200:
        return f"❌ Azure OCR error: {response.text}"

    result = response.json()

    # Extract text from response
    extracted_text = []
    for region in result.get("regions", []):
        for line in region.get("lines", []):
            line_text = " ".join([word["text"] for word in line["words"]])
            extracted_text.append(line_text)

    return "\n".join(extracted_text) if extracted_text else "❌ No text detected."

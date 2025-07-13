import os
import requests

AZURE_OCR_URL = "https://botocr.cognitiveservices.azure.com/vision/v3.2/read/analyze"
AZURE_KEY = os.getenv("AZURE_KEY")

def ocr_from_bytes(file_bytes: bytes):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }

    response = requests.post(AZURE_OCR_URL, headers=headers, data=file_bytes)

    if response.status_code != 200:
        print("Azure OCR Response:", response.text)
        return f"❌ Azure OCR error: {response.text}"

    result = response.json()

    # This assumes 'regions' exist — some newer Azure OCR APIs return different formats
    extracted_text = []
    try:
        for region in result.get("regions", []):
            for line in region.get("lines", []):
                line_text = " ".join([word["text"] for word in line["words"]])
                extracted_text.append(line_text)
    except KeyError:
        return "❌ Unexpected OCR response format."

    return "\n".join(extracted_text) if extracted_text else "❌ No text detected."


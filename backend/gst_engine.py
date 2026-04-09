import os
import json
import io
import base64
from PIL import Image
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY) if API_KEY else None

GST_EXTRACTION_PROMPT = """You are an expert GST invoice extraction engine for Indian retail and MSME invoices.

Extract ONLY valid JSON. If field not found return null.

Extract the following fields into a JSON object:
- gstin (string)
- invoice_number (string)
- invoice_date (string)
- taxable_value (number)
- cgst (number)
- sgst (number)
- igst (number)
- total_amount (number)
- ocr_confidence (number between 0 and 1 estimating confidence)
- tax_rates_found (array of numbers, e.g., if CGST@2.5%, extract [2.5])
- tax_breakdown_explicit (boolean)

Rules:
- If explicit CGST/SGST amounts are present, extract them and set tax_breakdown_explicit = true.
- If only tax rates (e.g., CGST@ 2.5%) are present but no tax totals:
  - Set tax_breakdown_explicit = false.
- If total_amount > taxable_value and no explicit tax totals exist:
  - Do NOT guess tax amounts.
  - Leave cgst, sgst, igst as null.
- Always return strict JSON. No explanations. No markdown.
"""

def extract_gst_invoice(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    if not client:
        raise ValueError("Gemini API key is not configured.")
        
    try:
        # Pre-process image with PIL to improve OCR
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to grayscale
        image = image.convert("L")
        # Apply thresholding
        image = image.point(lambda x: 0 if x < 140 else 255)
        
        # Save back to buffer
        buffered = io.BytesIO()
        img_format = image.format if image.format else "JPEG"
        if img_format == "JPEG" and image.mode != "RGB":
            image = image.convert("RGB") # Required for saving as JPEG
            
        image.save(buffered, format=img_format)
        processed_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[OCR] Warning: PIL preprocessing failed, falling back to original: {e}")
        processed_base64 = image_base64
        
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": GST_EXTRACTION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": processed_base64,
                        }
                    },
                ],
            }
        ],
    )
    
    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()
        
    return json.loads(raw_text)

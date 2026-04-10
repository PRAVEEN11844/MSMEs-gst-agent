import os
import json
import io
import base64
import re
from datetime import datetime
from PIL import Image
import pytesseract
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

def _fallback_ocr_extraction(image_bytes: bytes) -> dict:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        
        # Basic Regex rules for finding components
        gstin_match = re.search(r"([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1})", text, re.IGNORECASE)
        gstin = gstin_match.group(1).upper() if gstin_match else None
        
        date_match = re.search(r"([0-3][0-9][-/][0-1][0-9][-/][1-2][0-9]{3})", text)
        invoice_date = date_match.group(1) if date_match else None
        
        inv_match = re.search(r"(?:INV|INVOICE)(?:[^\dA-Z]*)([A-Z0-9-]+)", text, re.IGNORECASE)
        invoice_number = inv_match.group(1) if inv_match else f"FB-{int(datetime.now().timestamp())}"
        
        amount = 0.0
        lines = text.split("\n")
        amounts_found = []
        for line in lines:
            if "total" in line.lower() or "amount" in line.lower():
                num_matches = re.findall(r"[\d]+[.,][\d]{2}", line)
                for num in num_matches:
                    try:
                        amt_val = float(num.replace(",", ""))
                        amounts_found.append(amt_val)
                    except ValueError:
                        pass
        
        total_amount = max(amounts_found) if amounts_found else 0.0
        
        return {
            "gstin": gstin,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "taxable_value": 0.0,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "total_amount": total_amount,
            "ocr_confidence": 0.5,
            "tax_rates_found": [],
            "tax_breakdown_explicit": False,
            "is_fallback": True
        }
    except Exception as e:
        print(f"[OCR] Fallback OCR failed: {e}")
        return {
            "gstin": None,
            "invoice_number": f"ERR-{int(datetime.now().timestamp())}",
            "invoice_date": None,
            "taxable_value": 0.0,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "total_amount": 0.0,
            "ocr_confidence": 0.0,
            "tax_rates_found": [],
            "tax_breakdown_explicit": False,
            "is_fallback": True,
            "error_fallback": str(e)
        }

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
        
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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
        
    except Exception as e:
        print(f"[OCR] Gemini API failed: {e}. Executing OCR fallback.")
        return _fallback_ocr_extraction(base64.b64decode(image_base64))

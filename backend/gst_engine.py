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
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception
from google.genai.errors import APIError, ClientError

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

def get_raw_ocr_text(image_bytes: bytes) -> str:
    """Helper to get raw text for fallback."""
    try:
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            common_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(common_path):
                pytesseract.pytesseract.tesseract_cmd = common_path
            else:
                return "OCR Error: Tesseract not found."

        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"OCR Error: {str(e)}"

def _fallback_ocr_extraction(image_bytes: bytes) -> dict:
    try:
        text = get_raw_ocr_text(image_bytes)
        if not text or text.startswith("OCR Error"):
            raise Exception(text or "Empty OCR output")

        print(f"[OCR Fallback] Raw text:\n{text[:800]}")

        # ── GSTIN ──────────────────────────────────────────────
        gstin_match = re.search(
            r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9])\b",
            text, re.IGNORECASE
        )
        gstin = gstin_match.group(1).upper() if gstin_match else None

        # ── DATE ───────────────────────────────────────────────
        date_match = re.search(
            r"(?:date|dt|dated|invoice\s*date)[:\s]*"
            r"([0-3]?\d[-/\.][0-1]?\d[-/\.][0-9]{2,4})"
            r"|([0-3]?\d[-/\.][0-1]?\d[-/\.][0-9]{2,4})",
            text, re.IGNORECASE
        )
        invoice_date = None
        if date_match:
            invoice_date = (date_match.group(1) or date_match.group(2) or "").strip() or None

        # ── INVOICE NUMBER ─────────────────────────────────────
        inv_match = re.search(
            r"(?:invoice\s*(?:no|num|number|#)|inv\s*no|bill\s*no|"
            r"receipt\s*no|cash\s*memo)[:\s#]*([A-Z0-9][A-Z0-9\-/]{2,20})",
            text, re.IGNORECASE
        )
        invoice_number = inv_match.group(1).strip() if inv_match else None

        # ── COLLECT ALL NUMBERS ────────────────────────────────
        # Handles: 1,381.00 | 1381.00 | 13B1.00 (OCR error B→8)
        # Fix common OCR mistakes in numbers
        text_fixed = text.replace('B', '8').replace('O', '0').replace('l', '1')

        all_amounts = []
        for m in re.finditer(
            r"(?:₹|rs\.?|inr)?\s*([1-9][0-9]{0,6}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",
            text_fixed, re.IGNORECASE
        ):
            try:
                val = float(m.group(1).replace(",", ""))
                if 1 <= val <= 9999999:
                    all_amounts.append(val)
            except ValueError:
                continue

        # ── TOTAL AMOUNT ───────────────────────────────────────
        total = 0.0
        # Try labeled total first
        total_match = re.search(
            r"(?:grand\s*total|total\s*amount|net\s*(?:amount|payable)|"
            r"amount\s*(?:payable|due)|total\s*due|"
            r"bill\s*(?:amount|total)|total)[:\s₹Rs\.]*"
            r"([0-9,B]+\.?[0-9]{0,2})",   # B catches OCR error
            text_fixed, re.IGNORECASE
        )
        if total_match:
            raw = total_match.group(1).replace(",", "").replace("B", "8")
            try:
                total = float(raw)
            except ValueError:
                pass

        # Fallback: largest number on page
        if total == 0 and all_amounts:
            total = max(all_amounts)

        # ── CGST ───────────────────────────────────────────────
        cgst = 0.0
        # Handles: "CGST @ 2.5% = 122.40" or "CGST 6.38" or table format
        cgst_matches = re.findall(
            r"cgst[^0-9₹\n]{0,20}([0-9,]+\.?[0-9]{0,2})",
            text_fixed, re.IGNORECASE
        )
        if cgst_matches:
            vals = []
            for m in cgst_matches:
                try:
                    v = float(m.replace(",", ""))
                    if v < 1000:   # Ignore huge numbers (likely amounts not rates)
                        vals.append(v)
                except ValueError:
                    continue
            if vals:
                cgst = sum(vals)   # Sum all CGST entries (multiple tax rates)

        # ── SGST ───────────────────────────────────────────────
        sgst = 0.0
        sgst_matches = re.findall(
            r"sgst[^0-9₹\n]{0,20}([0-9,]+\.?[0-9]{0,2})",
            text_fixed, re.IGNORECASE
        )
        if sgst_matches:
            vals = []
            for m in sgst_matches:
                try:
                    v = float(m.replace(",", ""))
                    if v < 1000:
                        vals.append(v)
                except ValueError:
                    continue
            if vals:
                sgst = sum(vals)

        # ── IGST ───────────────────────────────────────────────
        igst = 0.0
        igst_match = re.search(
            r"igst[^0-9₹\n]{0,20}([0-9,]+\.?[0-9]{0,2})",
            text_fixed, re.IGNORECASE
        )
        if igst_match:
            try:
                igst = float(igst_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # ── TAXABLE VALUE ──────────────────────────────────────
        taxable = 0.0
        taxable_match = re.search(
            r"(?:taxable\s*(?:value|amount|amt)|"
            r"base\s*(?:amount|amt)|subtotal|sub\s*total|"
            r"taxable)[:\s₹Rs\.]*([0-9,]+\.?[0-9]{0,2})",
            text_fixed, re.IGNORECASE
        )
        if taxable_match:
            try:
                taxable = float(taxable_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # ── SMART INFERENCE ────────────────────────────────────
        if total > 0 and taxable == 0 and cgst == 0 and sgst == 0:
            # No taxes found → assume 18% GST (most common)
            taxable = round(total * 100 / 118, 2)
            tax     = round(total - taxable, 2)
            cgst    = round(tax / 2, 2)
            sgst    = round(tax / 2, 2)
            print(f"[OCR] Inferred 18% GST: taxable={taxable} cgst={cgst} sgst={sgst}")

        elif total > 0 and taxable == 0 and (cgst > 0 or sgst > 0):
            # Have taxes but no taxable — back-calculate
            taxable = round(total - cgst - sgst - igst, 2)

        print(f"[OCR] Result → invoice={invoice_number} total={total} "
              f"taxable={taxable} cgst={cgst} sgst={sgst} gstin={gstin}")

        return {
            "gstin":                  gstin,
            "invoice_number":         invoice_number,
            "invoice_date":           invoice_date,
            "taxable_value":          taxable,
            "cgst":                   cgst,
            "sgst":                   sgst,
            "igst":                   igst,
            "total_amount":           total,
            "ocr_confidence":         0.5,
            "tax_rates_found":        [],
            "tax_breakdown_explicit": (cgst > 0 or sgst > 0 or igst > 0),
            "is_fallback":            True,
        }

    except Exception as e:
        print(f"[OCR Fallback] Failed: {e}")
        return {
            "gstin": None, "invoice_number": None,
            "invoice_date": None, "taxable_value": 0.0,
            "cgst": 0.0, "sgst": 0.0, "igst": 0.0,
            "total_amount": 0.0, "ocr_confidence": 0.0,
            "tax_rates_found": [], "tax_breakdown_explicit": False,
            "is_fallback": True, "error_fallback": str(e)
        }


def extract_gst_invoice(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    # No Gemini client → go straight to structured OCR fallback
    if not client:
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            image_bytes = b""
        return {
            "success": True,
            "error": "Gemini API key not configured — OCR fallback used",
            "fallback_used": True,
            "data": _fallback_ocr_extraction(image_bytes)
        }

    # Step 1: PIL preprocessing
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("L")
        image = image.point(lambda x: 0 if x < 140 else 255)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        processed_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        processed_mime_type = "image/png"
        print(f"[OCR] PIL preprocessing OK → PNG ({len(buffered.getvalue())} bytes)")
    except Exception as e:
        print(f"[ERROR] PIL preprocessing failed, using original: {e}")
        processed_base64 = image_base64
        processed_mime_type = mime_type
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            image_bytes = b""

    # Step 2: Try Gemini with model cascade — skip retries on quota/auth errors
    MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.5-flash"]

    for model_name in MODELS_TO_TRY:
        try:
            @retry(
                stop=stop_after_attempt(2),
                wait=wait_fixed(1),
                retry=retry_if_exception(lambda e: not isinstance(e, (ClientError, APIError)))
            )
            def extract_with_retry(m=model_name):
                response = client.models.generate_content(
                    model=m,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": GST_EXTRACTION_PROMPT},
                                {
                                    "inline_data": {
                                        "mime_type": processed_mime_type,
                                        "data": processed_base64,
                                    }
                                },
                            ],
                        }
                    ],
                )
                resp_text = response.text.strip()
                if resp_text.startswith("```"):
                    resp_text = resp_text.split("\n", 1)[1]
                    resp_text = resp_text.rsplit("```", 1)[0].strip()
                return json.loads(resp_text)

            result = extract_with_retry()
            print(f"[GST Engine] Extracted with {model_name}")
            return {
                "success": True,
                "error": None,
                "fallback_used": False,
                "model_used": model_name,
                "data": result,
            }

        except (ClientError, APIError) as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                print(f"[GST Engine] {model_name} quota exceeded — trying next model")
                continue   # try next model in cascade
            elif "403" in msg:
                print(f"[GST Engine] {model_name} auth failed — trying next model")
                continue
            else:
                print(f"[GST Engine] {model_name} API error: {msg[:150]}")
                break      # non-quota error, skip cascade and go to OCR

        except Exception as e:
            print(f"[GST Engine] {model_name} failed: {e} — trying next model")
            continue

    # All Gemini models exhausted — use OCR fallback
    print("[GST Engine] All Gemini models exhausted — using OCR fallback")
    return {
        "success": True,
        "error": "Gemini quota exceeded on all models — OCR fallback used",
        "fallback_used": True,
        "data": _fallback_ocr_extraction(image_bytes),
    }


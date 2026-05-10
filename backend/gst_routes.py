from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import base64
import re
from datetime import datetime
from database import gst_invoices_collection
from gst_engine import extract_gst_invoice
from gst_summary import get_monthly_gst_summary
from gstr1_export import export_gstr1_csv
from pymongo.errors import DuplicateKeyError

router = APIRouter()

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}$"

def parse_num(val):
    if val is None:
        return 0.0
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("₹", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def clean_gstin(raw_gstin: str) -> str:
    if not raw_gstin:
        return ""

    cleaned = str(raw_gstin).replace(" ", "").upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)

    res = []
    for i, char in enumerate(cleaned):
        # GSTIN structure: 0-1 = state code (numeric), 2-6 = PAN letters,
        # 7-10 = PAN digits, 11 = entity type (alpha/num),
        # 12 = ALWAYS 'Z' per spec, 13 = check digit
        is_numeric_position = i in [0, 1, 7, 8, 9, 10]
        is_always_z = (i == 12)

        if is_always_z:
            res.append('Z')           # Force 'Z' — never convert it to '2'
        elif is_numeric_position:
            if char == 'O': char = '0'
            elif char == 'I': char = '1'
            elif char == 'S': char = '5'
            elif char == 'Z': char = '2'  # Z→2 only valid at numeric positions
            res.append(char)
        else:
            res.append(char)

    return "".join(res)

@router.post("/analyze")
async def analyze_gst_invoice(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        mime_type = file.content_type or "image/jpeg"
        b64_data = base64.b64encode(contents).decode("utf-8")
        
        extraction_result = extract_gst_invoice(b64_data, mime_type)
        
        # Both Gemini success and OCR fallback now return structured dicts —
        # run both through the same validation pipeline (no early return).

        success = extraction_result.get("success", False)
        fallback_used = extraction_result.get("fallback_used", False)
        extracted_data = extraction_result.get("data", {}) or {}
        extraction_error = extraction_result.get("error")

        # Validation and cleanup (same path for Gemini AND fallback data)
        raw_gstin = extracted_data.get("gstin", "") or ""
        cleaned_gstin = clean_gstin(raw_gstin)
        extracted_data["gstin"] = cleaned_gstin

        gstin_valid = bool(re.match(GSTIN_REGEX, cleaned_gstin))
        extracted_data["gstin_valid"] = gstin_valid

        taxable = parse_num(extracted_data.get("taxable_value"))
        cgst    = parse_num(extracted_data.get("cgst"))
        sgst    = parse_num(extracted_data.get("sgst"))
        igst    = parse_num(extracted_data.get("igst"))
        total   = parse_num(extracted_data.get("total_amount"))

        extracted_data["taxable_value"] = taxable
        extracted_data["cgst"]          = cgst
        extracted_data["sgst"]          = sgst
        extracted_data["igst"]          = igst
        extracted_data["total_amount"]  = total

        tax_breakdown_explicit = extracted_data.get("tax_breakdown_explicit", True)
        tax_rates_found        = extracted_data.get("tax_rates_found", [])
        tax_inferred           = False

        if not tax_breakdown_explicit:
            if total > 0 and taxable > 0:
                inferred_tax = total - taxable
                if inferred_tax > 0:
                    extracted_data["cgst"] = round(inferred_tax / 2, 2)
                    extracted_data["sgst"] = round(inferred_tax / 2, 2)
                    extracted_data["igst"] = 0
                    tax_inferred = True
            elif total > 0 and not taxable and len(tax_rates_found) == 1:
                tax_rate      = tax_rates_found[0]
                combined_rate = tax_rate * 2
                base_value    = total * 100 / (100 + combined_rate)
                inferred_tax  = total - base_value
                extracted_data["taxable_value"] = round(base_value, 2)
                extracted_data["cgst"]          = round(inferred_tax / 2, 2)
                extracted_data["sgst"]          = round(inferred_tax / 2, 2)
                extracted_data["igst"]          = 0
                tax_inferred = True

        extracted_data["tax_inferred"]   = tax_inferred
        extracted_data["fallback_used"]  = fallback_used

        # Refresh after inference
        taxable = extracted_data["taxable_value"]
        cgst    = extracted_data["cgst"]
        sgst    = extracted_data["sgst"]
        igst    = extracted_data["igst"]

        calculated_total = taxable + cgst + sgst + igst
        extracted_data["tax_warning"] = abs(calculated_total - total) > 1.0
        extracted_data["created_at"]  = datetime.now().isoformat()

        # Handle missing invoice_number
        if not extracted_data.get("invoice_number"):
            if fallback_used:
                # OCR fallback: auto-assign placeholder so we don't reject it
                extracted_data["invoice_number"] = f"FB-{int(datetime.now().timestamp())}"
                print(f"[GST] Fallback invoice auto-numbered: {extracted_data['invoice_number']}")
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "data": None,
                        "error": "validation_error: Missing invoice number",
                        "fallback_used": fallback_used
                    }
                )

        try:
            if gst_invoices_collection is not None:
                inv_num = extracted_data.get("invoice_number", "")
                total   = extracted_data.get("total_amount", 0)

                # Only block if ERR- AND total=0 (OCR extracted nothing useful)
                # FB- records with real data (total > 0) MUST be stored
                is_useless = inv_num.startswith("ERR-") and total == 0

                if is_useless:
                    print(f"[MongoDB] Skipping useless ERR-/zero record: {inv_num!r}")
                    return JSONResponse(
                        status_code=422,
                        content={
                            "success": False,
                            "data": None,
                            "error": "Could not extract any data from this image. Please upload a clearer GST invoice photo.",
                            "fallback_used": fallback_used,
                            "tip": "Ensure the invoice is well-lit, not blurry, and the full invoice is visible."
                        }
                    )

                gst_invoices_collection.insert_one(dict(extracted_data))
                print(f"[MongoDB] Stored GST invoice: {inv_num} | total={total}")

        except DuplicateKeyError:
            print(f"[MongoDB] Duplicate invoice skipped: {extracted_data.get('invoice_number')}")
        except Exception as db_err:
            print(f"[MongoDB] DB insert failed (non-fatal): {db_err}")

        # Clean _id for JSON response
        if "_id" in extracted_data:
            extracted_data["_id"] = str(extracted_data["_id"])

        return JSONResponse(content={
            "success": success,
            "data": extracted_data,
            "error": extraction_error,
            "fallback_used": fallback_used
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500, 
            content={"success": False, "data": None, "error": f"Internal Server Error in Analyze: {str(e)}", "fallback_used": False}
        )

@router.delete("/invoices/cleanup")
async def cleanup_junk_invoices():
    """Remove all ERR- prefixed and zero-value FB- invoices from MongoDB."""
    try:
        if gst_invoices_collection is None:
            return JSONResponse(content={"success": False, "error": "DB not available"})

        err_result = gst_invoices_collection.delete_many(
            {"invoice_number": {"$regex": "^ERR-"}}
        )
        fb_result = gst_invoices_collection.delete_many({
            "invoice_number": {"$regex": "^FB-"},
            "total_amount": 0,
            "taxable_value": 0
        })

        total_deleted = err_result.deleted_count + fb_result.deleted_count
        print(f"[MongoDB] Cleanup: deleted {total_deleted} junk records "
              f"(ERR={err_result.deleted_count}, FB-zero={fb_result.deleted_count})")

        return JSONResponse(content={
            "success": True,
            "deleted": total_deleted,
            "err_deleted": err_result.deleted_count,
            "fb_deleted": fb_result.deleted_count
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.delete("/invoices/all")
async def delete_all_invoices():
    """Delete ALL GST invoices — used for demo resets."""
    try:
        if gst_invoices_collection is None:
            return JSONResponse(content={"success": False, "error": "DB not available"})
        result = gst_invoices_collection.delete_many({})
        print(f"[MongoDB] Deleted ALL {result.deleted_count} GST invoices")
        return JSONResponse(content={"success": True, "deleted": result.deleted_count})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.get("/invoices")
async def get_gst_invoices():
    try:
        if gst_invoices_collection is None:
            return JSONResponse(content={"success": True, "data": [], "error": "DB not available"})
        invoices = list(gst_invoices_collection.find({}, {"_id": 0}))
        return JSONResponse(content={"success": True, "data": invoices, "error": None})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})

@router.get("/invoice/{invoice_number}")
async def get_single_invoice(invoice_number: str):
    try:
        if gst_invoices_collection is None:
            return JSONResponse(status_code=404, content={"success": False, "data": None, "error": "DB not available"})
        invoice = gst_invoices_collection.find_one({"invoice_number": invoice_number}, {"_id": 0})
        if not invoice:
            return JSONResponse(status_code=404, content={"success": False, "data": None, "error": "Invoice not found"})
        return JSONResponse(content={"success": True, "data": invoice, "error": None})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})

@router.get("/summary/monthly")
async def get_gst_summary():
    try:
        summary = get_monthly_gst_summary()
        return JSONResponse(content={"success": True, "data": summary, "error": None})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})

@router.get("/export")
async def export_gstr1():
    try:
        return export_gstr1_csv()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})

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
    
    # Remove spaces and turn to upper
    cleaned = str(raw_gstin).replace(" ", "").upper()
    # Strip non-alphanumeric
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    
    # Correct character positions
    res = []
    for i, char in enumerate(cleaned):
        is_numeric = i in [0, 1, 7, 8, 9, 10]
        if is_numeric:
            if char == 'O': char = '0'
            elif char == 'I': char = '1'
            elif char == 'S': char = '5'
            elif char == 'Z': char = '2'
        res.append(char)
        
    return "".join(res)

@router.post("/analyze")
async def analyze_gst_invoice(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        mime_type = file.content_type or "image/jpeg"
        b64_data = base64.b64encode(contents).decode("utf-8")
        
        extracted_data = extract_gst_invoice(b64_data, mime_type)
        
        # Validation and cleanup
        raw_gstin = extracted_data.get("gstin", "")
        cleaned_gstin = clean_gstin(raw_gstin)
        extracted_data["gstin"] = cleaned_gstin
        
        gstin_valid = bool(re.match(GSTIN_REGEX, cleaned_gstin))
        extracted_data["gstin_valid"] = gstin_valid
            
        taxable = parse_num(extracted_data.get("taxable_value"))
        cgst = parse_num(extracted_data.get("cgst"))
        sgst = parse_num(extracted_data.get("sgst"))
        igst = parse_num(extracted_data.get("igst"))
        total = parse_num(extracted_data.get("total_amount"))
        
        extracted_data["taxable_value"] = taxable
        extracted_data["cgst"] = cgst
        extracted_data["sgst"] = sgst
        extracted_data["igst"] = igst
        extracted_data["total_amount"] = total
        
        tax_breakdown_explicit = extracted_data.get("tax_breakdown_explicit", True)
        tax_rates_found = extracted_data.get("tax_rates_found", [])
        tax_inferred = False

        if not tax_breakdown_explicit:
            if total > 0 and taxable > 0:
                inferred_tax = total - taxable
                if inferred_tax > 0:
                    # Assume intra-state (CGST + SGST split)
                    extracted_data["cgst"] = inferred_tax / 2
                    extracted_data["sgst"] = inferred_tax / 2
                    extracted_data["igst"] = 0
                    tax_inferred = True
            elif total > 0 and not taxable and len(tax_rates_found) == 1:
                # Advanced: Single rate, tax inclusive total
                tax_rate = tax_rates_found[0]
                # If rate is e.g. 5, then total is 105% of base
                combined_rate = tax_rate * 2 # if CGST is 2.5, total rate is 5
                base_value = total * 100 / (100 + combined_rate)
                inferred_tax = total - base_value
                
                extracted_data["taxable_value"] = round(base_value, 2)
                extracted_data["cgst"] = round(inferred_tax / 2, 2)
                extracted_data["sgst"] = round(inferred_tax / 2, 2)
                extracted_data["igst"] = 0
                tax_inferred = True
                
        extracted_data["tax_inferred"] = tax_inferred
        
        # update vars for validation
        taxable = extracted_data["taxable_value"]
        cgst = extracted_data["cgst"]
        sgst = extracted_data["sgst"]
        igst = extracted_data["igst"]

        # Tax validation with tolerance
        calculated_total = taxable + cgst + sgst + igst
        if abs(calculated_total - total) > 1.0:
            extracted_data["tax_warning"] = True
        else:
            extracted_data["tax_warning"] = False
            
        extracted_data["created_at"] = datetime.now().isoformat()
        
        if not extracted_data.get("invoice_number"):
            return JSONResponse(status_code=400, content={"success": False, "data": None, "error": "validation_error: Missing invoice number"})
            
        if gst_invoices_collection is not None:
            try:
                gst_invoices_collection.insert_one(dict(extracted_data))
            except DuplicateKeyError:
                return JSONResponse(status_code=409, content={"success": False, "data": None, "error": "duplicate_error: Invoice already exists"})
                
        # Clean _id for JSON response
        if "_id" in extracted_data:
            extracted_data["_id"] = str(extracted_data["_id"])
            
        return JSONResponse(content={"success": True, "data": extracted_data, "error": None})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})

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

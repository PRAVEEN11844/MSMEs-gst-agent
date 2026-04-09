import pandas as pd
import io
from fastapi.responses import StreamingResponse
from database import gst_invoices_collection

def export_gstr1_csv():
    invoices = []
    if gst_invoices_collection is not None:
        invoices = list(gst_invoices_collection.find({}, {"_id": 0}))
        
    if not invoices:
        df = pd.DataFrame(columns=["GSTIN", "Invoice Number", "Invoice Date", "Taxable Value", "CGST", "SGST", "IGST", "Total Amount"])
    else:
        df = pd.DataFrame(invoices)
        df = df.rename(columns={
            "gstin": "GSTIN",
            "invoice_number": "Invoice Number",
            "invoice_date": "Invoice Date",
            "taxable_value": "Taxable Value",
            "cgst": "CGST",
            "sgst": "SGST",
            "igst": "IGST",
            "total_amount": "Total Amount"
        })
        cols = ["GSTIN", "Invoice Number", "Invoice Date", "Taxable Value", "CGST", "SGST", "IGST", "Total Amount"]
        df = df[[c for c in cols if c in df.columns]]
    
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=gstr1_export.csv"
    return response

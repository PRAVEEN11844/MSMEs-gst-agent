from database import gst_invoices_collection

def get_monthly_gst_summary() -> dict:
    invoices = []
    if gst_invoices_collection is not None:
        invoices = list(gst_invoices_collection.find({}, {"_id": 0}))
    
    total_revenue = sum(inv.get("taxable_value") or 0 for inv in invoices)
    total_cgst = sum(inv.get("cgst") or 0 for inv in invoices)
    total_sgst = sum(inv.get("sgst") or 0 for inv in invoices)
    total_igst = sum(inv.get("igst") or 0 for inv in invoices)
    total_gst_liability = total_cgst + total_sgst + total_igst
    invoice_count = len(invoices)
    
    return {
        "total_revenue": total_revenue,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "total_gst_liability": total_gst_liability,
        "invoice_count": invoice_count
    }

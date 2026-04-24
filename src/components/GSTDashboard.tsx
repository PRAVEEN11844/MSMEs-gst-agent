import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    Wallet, TrendingDown, Receipt, PiggyBank,
    Download, FilePlus2, Sparkles, Trash2,
    AlertTriangle, RotateCcw,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GSTUpload from "@/components/GSTUpload";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { useGSTStore, fetchGSTInvoices, fetchGSTSummary } from "@/lib/gst-store";

const defaultKpis = [
    { title: "Total Revenue",       value: "₹0", change: "0 items", trend: "up"   as const, icon: Wallet      },
    { title: "Total GST Liability", value: "₹0", change: "",        trend: "down" as const, icon: Receipt     },
    { title: "CGST Collected",      value: "₹0", change: "",        trend: "up"   as const, icon: PiggyBank   },
    { title: "SGST Collected",      value: "₹0", change: "",        trend: "up"   as const, icon: TrendingDown },
];

function computeKpis(summary: {
    total_revenue: number;
    total_gst_liability: number;
    total_cgst: number;
    total_sgst: number;
    invoice_count: number;
}) {
    return [
        { title: "Total Revenue",       value: `₹${summary.total_revenue.toLocaleString("en-IN")}`,       change: `${summary.invoice_count} invoices`, trend: "up"   as const, icon: Wallet      },
        { title: "Total GST Liability", value: `₹${summary.total_gst_liability.toLocaleString("en-IN")}`, change: "Payable",                           trend: "down" as const, icon: Receipt     },
        { title: "CGST Collected",      value: `₹${summary.total_cgst.toLocaleString("en-IN")}`,          change: "",                                  trend: "up"   as const, icon: PiggyBank   },
        { title: "SGST Collected",      value: `₹${summary.total_sgst.toLocaleString("en-IN")}`,          change: "",                                  trend: "up"   as const, icon: TrendingDown },
    ];
}

const GSTDashboard = () => {
    const { invoices, summary } = useGSTStore();

    // ✅ Fix 1: ALL hooks declared at the top — before any derived variables
    const [isOCRMode, setIsOCRMode] = useState(false);

    useEffect(() => {
        fetchGSTInvoices();
        fetchGSTSummary();
    }, []);

    // ✅ Fix 4: Correct dependency array — only re-runs when invoices changes
    useEffect(() => {
        // ✅ Fix 2: Direct field access — fallback_used is now typed in GSTInvoice
        const anyFallback = invoices.some((inv) => inv.fallback_used || inv.is_fallback);
        setIsOCRMode(anyFallback);
    }, [invoices]);

    // Derived values come AFTER all hooks
    const hasData = invoices.length > 0;
    const kpis    = summary ? computeKpis(summary) : defaultKpis;

    // ✅ Fix 3: Correct endpoint — DELETE /api/gst/invoices/all (not /api/gst/invoices)
    const handleClearAll = async () => {
        if (!confirm("Clear ALL GST invoice data? This cannot be undone.")) return;
        try {
            const res  = await fetch("/api/gst/invoices/all", { method: "DELETE" });
            const data = await res.json();
            if (data.success) {
                toast({ title: `🗑️ Cleared ${data.deleted} invoice(s)` });
                await fetchGSTInvoices();
                await fetchGSTSummary();
                setIsOCRMode(false);
            } else {
                throw new Error(data.error ?? "Delete failed");
            }
        } catch (e) {
            toast({ title: "Clear failed", description: String(e), variant: "destructive" });
        }
    };

    const handleCleanup = async () => {
        try {
            const res  = await fetch("/api/gst/invoices/cleanup", { method: "DELETE" });
            const data = await res.json();
            if (data.success) {
                toast({ title: `🧹 Cleaned up ${data.deleted} junk record(s)` });
                await fetchGSTInvoices();
                await fetchGSTSummary();
            } else {
                toast({ title: "Cleanup failed", description: data.error, variant: "destructive" });
            }
        } catch (e) {
            toast({ title: "Cleanup error", description: String(e), variant: "destructive" });
        }
    };

    const handleExport = () => {
        window.open("/api/gst/export", "_blank");
    };

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex justify-between items-end flex-wrap gap-3"
            >
                <div>
                    <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                        <FilePlus2 className="w-6 h-6 text-primary" />
                        MSME GST Portal
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {hasData
                            ? "GST Extraction & Filing Intelligence"
                            : "Upload your MSME GSTR invoices to begin"}
                    </p>
                </div>

                {hasData && (
                    <div className="flex items-center gap-2 flex-wrap">
                        <Button
                            variant="outline"
                            onClick={handleClearAll}
                            className="gap-2 text-muted-foreground border-border hover:bg-muted/30"
                        >
                            <RotateCcw className="w-4 h-4" /> Clear All
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleCleanup}
                            className="gap-2 text-destructive border-destructive hover:bg-destructive/10"
                        >
                            <Trash2 className="w-4 h-4" /> Remove Junk
                        </Button>
                        <Button onClick={handleExport} className="gap-2">
                            <Download className="w-4 h-4" /> Export GSTR-1 (CSV)
                        </Button>
                    </div>
                )}
            </motion.div>

            {/* OCR Mode Banner */}
            {isOCRMode && (
                <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-sm text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>
                        Running in OCR mode — Gemini quota reached.
                        Data accuracy may be lower; please verify extracted values.
                    </span>
                </div>
            )}

            {/* Upload Zone */}
            <GSTUpload />

            {/* KPIs */}
            <h2 className="text-lg font-semibold mt-8 mb-4">Monthly Analytics</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {kpis.map((kpi, i) => (
                    <KPICard key={kpi.title} {...kpi} index={i} />
                ))}
            </div>

            {/* Invoice Table */}
            {hasData && (
                <div className="mt-8 space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold">
                            Extracted GST Invoices
                            <span className="ml-2 text-sm font-normal text-muted-foreground">
                                ({invoices.length} records)
                            </span>
                        </h2>
                    </div>

                    <div className="bg-card border rounded-xl overflow-hidden shadow-sm">
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs uppercase bg-muted/50 border-b">
                                    <tr>
                                        <th className="px-6 py-4 font-medium text-muted-foreground">Invoice No.</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground">GSTIN</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground">Date</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground text-right">Taxable</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground text-right">GST Total</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground text-right">Net Amount</th>
                                        <th className="px-6 py-4 font-medium text-muted-foreground text-center">Flags</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {invoices.map((inv) => (
                                        <tr
                                            key={inv.invoice_number}
                                            className="bg-card hover:bg-muted/30 transition-colors"
                                        >
                                            <td className="px-6 py-4 font-medium font-mono text-xs">
                                                {inv.invoice_number}
                                            </td>
                                            <td className="px-6 py-4 font-mono text-xs">
                                                {inv.gstin || "—"}
                                            </td>
                                            <td className="px-6 py-4">
                                                {inv.invoice_date || "—"}
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                ₹{(inv.taxable_value ?? 0).toLocaleString("en-IN")}
                                            </td>
                                            <td className="px-6 py-4 text-right text-muted-foreground">
                                                ₹{((inv.cgst ?? 0) + (inv.sgst ?? 0) + (inv.igst ?? 0)).toLocaleString("en-IN")}
                                            </td>
                                            <td className="px-6 py-4 text-right font-semibold">
                                                ₹{(inv.total_amount ?? 0).toLocaleString("en-IN")}
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <div className="flex flex-wrap gap-1 justify-center">
                                                    {inv.tax_warning ? (
                                                        <span className="px-2 py-1 bg-destructive/10 text-destructive text-xs rounded-full font-medium">
                                                            ⚠ Warning
                                                        </span>
                                                    ) : (
                                                        <span className="px-2 py-1 bg-green-500/10 text-green-600 text-xs rounded-full font-medium">
                                                            ✓ Valid
                                                        </span>
                                                    )}
                                                    {inv.tax_inferred && (
                                                        <span className="px-2 py-1 bg-blue-500/10 text-blue-600 text-xs rounded-full font-medium inline-flex items-center gap-1">
                                                            <Sparkles className="w-3 h-3" /> Inferred
                                                        </span>
                                                    )}
                                                    {/* ✅ Fix 2: No type cast — field is now in GSTInvoice */}
                                                    {(inv.fallback_used || inv.is_fallback) && (
                                                        <span className="px-2 py-1 bg-amber-500/10 text-amber-600 text-xs rounded-full font-medium">
                                                            OCR
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default GSTDashboard;

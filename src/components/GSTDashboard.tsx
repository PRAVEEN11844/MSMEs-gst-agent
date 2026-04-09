import { useEffect } from "react";
import { motion } from "framer-motion";
import { Wallet, TrendingDown, Receipt, PiggyBank, Download, FilePlus2, Sparkles } from "lucide-react";
import KPICard from "@/components/KPICard";
import GSTUpload from "@/components/GSTUpload";
import { Button } from "@/components/ui/button";
import { useGSTStore, fetchGSTInvoices, fetchGSTSummary } from "@/lib/gst-store";

const defaultKpis = [
    { title: "Total Revenue", value: "₹0", change: "0 items", trend: "up" as const, icon: Wallet },
    { title: "Total GST Liability", value: "₹0", change: "", trend: "down" as const, icon: Receipt },
    { title: "CGST", value: "₹0", change: "", trend: "up" as const, icon: PiggyBank },
    { title: "SGST", value: "₹0", change: "", trend: "up" as const, icon: TrendingDown },
];

function computeKpis(summary: { total_revenue: number, total_gst_liability: number, total_cgst: number, total_sgst: number, invoice_count: number }) {
    return [
        { title: "Total Revenue", value: `₹${summary.total_revenue.toLocaleString("en-IN")}`, change: `${summary.invoice_count} invoices`, trend: "up" as const, icon: Wallet },
        { title: "Total GST Liability", value: `₹${summary.total_gst_liability.toLocaleString("en-IN")}`, change: "Payable", trend: "down" as const, icon: Receipt },
        { title: "CGST Collected", value: `₹${summary.total_cgst.toLocaleString("en-IN")}`, change: "", trend: "up" as const, icon: PiggyBank },
        { title: "SGST Collected", value: `₹${summary.total_sgst.toLocaleString("en-IN")}`, change: "", trend: "up" as const, icon: TrendingDown },
    ];
}

const GSTDashboard = () => {
    const { invoices, summary } = useGSTStore();

    useEffect(() => {
        fetchGSTInvoices();
        fetchGSTSummary();
    }, []);

    const hasData = invoices.length > 0;
    const kpis = summary ? computeKpis(summary) : defaultKpis;

    const handleExport = () => {
        window.open("/api/gst/export", "_blank");
    };

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                        <FilePlus2 className="w-6 h-6 text-primary" />
                        MSME GST Portal
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {hasData ? "GST Extraction & Filing Intelligence" : "Upload your MSME GSTR invoices to begin"}
                    </p>
                </div>

                {hasData && (
                    <Button onClick={handleExport} className="gap-2">
                        <Download className="w-4 h-4" /> Export GSTR-1 (CSV)
                    </Button>
                )}
            </motion.div>

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
                    <h2 className="text-lg font-semibold">Extracted GST Invoices</h2>
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
                                        <tr key={inv.invoice_number} className="bg-card hover:bg-muted/30 transition-colors">
                                            <td className="px-6 py-4 font-medium">{inv.invoice_number}</td>
                                            <td className="px-6 py-4">{inv.gstin}</td>
                                            <td className="px-6 py-4">{inv.invoice_date}</td>
                                            <td className="px-6 py-4 text-right">₹{inv.taxable_value?.toLocaleString("en-IN") || 0}</td>
                                            <td className="px-6 py-4 text-right text-muted-foreground">
                                                ₹{(inv.cgst + inv.sgst + inv.igst).toLocaleString("en-IN")}
                                            </td>
                                            <td className="px-6 py-4 text-right font-semibold">₹{inv.total_amount?.toLocaleString("en-IN") || 0}</td>
                                            <td className="px-6 py-4 text-center">
                                                {inv.tax_warning ? (
                                                    <span className="px-2 py-1 bg-destructive/10 text-destructive text-xs rounded-full font-medium">Warning</span>
                                                ) : (
                                                    <span className="px-2 py-1 bg-green-500/10 text-green-600 text-xs rounded-full font-medium">Valid</span>
                                                )}
                                                {inv.tax_inferred && (
                                                    <span className="px-2 py-1 bg-blue-500/10 text-blue-600 text-xs rounded-full font-medium ml-1 inline-flex items-center gap-1 mt-1 lg:mt-0">
                                                        <Sparkles className="w-3 h-3" /> Inferred
                                                    </span>
                                                )}
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

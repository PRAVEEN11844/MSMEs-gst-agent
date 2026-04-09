import { useEffect } from "react";
import { motion } from "framer-motion";
import { Wallet, TrendingDown, Receipt, PiggyBank, CalendarClock, Loader2 } from "lucide-react";
import KPICard from "@/components/KPICard";
import TransactionsTable from "@/components/TransactionsTable";
import ChatInterface from "@/components/ChatInterface";
import SpendingChart from "@/components/SpendingChart";
import SuggestionCard from "@/components/SuggestionCard";
import { useAnalyzeStore, fetchTransactions } from "@/lib/analyze-store";
import { useReminderStore, createReminder } from "@/lib/reminder-store";

const defaultKpis = [
  { title: "Total Spent This Month", value: "₹14,520", change: "12%", trend: "down" as const, icon: Wallet },
  { title: "Average Transaction", value: "₹631", change: "5%", trend: "up" as const, icon: Receipt },
  { title: "Recurring Payments", value: "₹1,167", change: "0%", trend: "up" as const, icon: TrendingDown },
  { title: "Estimated Savings", value: "₹4,480", change: "8%", trend: "up" as const, icon: PiggyBank },
];

function computeKpis(transactions: { amount: string }[]) {
  // Parse amounts: strip currency symbols and commas, e.g. "₹2,499" → 2499
  const amounts = transactions.map((tx) => {
    const num = parseFloat(tx.amount.replace(/[^0-9.\-]/g, ""));
    return isNaN(num) ? 0 : num;
  });

  const total = amounts.reduce((sum, a) => sum + a, 0);
  const avg = amounts.length > 0 ? Math.round(total / amounts.length) : 0;

  return [
    { title: "Total Spent", value: `₹${total.toLocaleString("en-IN")}`, change: `${amounts.length} items`, trend: "down" as const, icon: Wallet },
    { title: "Average Transaction", value: `₹${avg.toLocaleString("en-IN")}`, change: "", trend: "up" as const, icon: Receipt },
    { title: "Transactions Found", value: `${amounts.length}`, change: "OCR", trend: "up" as const, icon: TrendingDown },
    { title: "Highest Amount", value: `₹${Math.max(...amounts, 0).toLocaleString("en-IN")}`, change: "", trend: "up" as const, icon: PiggyBank },
  ];
}

const Dashboard = () => {
  const { transactions, ocrConfidence, updateTransaction } = useAnalyzeStore();
  const { recurringPayments, isDetecting, detectRecurring } = useReminderStore();

  const hasRealData = transactions.length > 0;
  const kpis = hasRealData ? computeKpis(transactions) : defaultKpis;

  // Fetch persisted transactions from DB on mount
  useEffect(() => {
    fetchTransactions();
  }, []);

  // Auto-detect recurring transactions when data is available
  useEffect(() => {
    if (transactions.length > 1) {
      detectRecurring(transactions);
    }
  }, [transactions]);

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h1 className="text-xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {hasRealData
            ? `Showing extracted data · ${ocrConfidence !== null ? Math.round(ocrConfidence * 100) : "—"}% OCR confidence`
            : "Your financial overview at a glance"}
        </p>
      </motion.div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => (
          <KPICard key={kpi.title} {...kpi} index={i} />
        ))}
      </div>

      {/* Recurring Payment Suggestions */}
      {(isDetecting || recurringPayments.length > 0) && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-primary" /> Recurring Payment Suggestions
          </h2>
          {isDetecting ? (
            <div className="flex items-center gap-2 py-4">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">Detecting recurring payments...</span>
            </div>
          ) : (
            recurringPayments.map((item, i) => (
              <SuggestionCard
                key={item.merchant}
                merchant={item.merchant}
                amount={item.average_amount}
                frequency={item.frequency_days}
                nextDue={item.next_due_date}
                onEnable={() => createReminder(item)}
                index={i}
              />
            ))
          )}
        </div>
      )}

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <TransactionsTable
            transactions={hasRealData ? transactions : undefined}
            onUpdateTransaction={hasRealData ? updateTransaction : undefined}
          />
        </div>
        <div className="lg:col-span-1">
          <ChatInterface compact />
        </div>
      </div>

      {/* Charts */}
      <SpendingChart transactions={hasRealData ? transactions : undefined} />
    </div>
  );
};

export default Dashboard;


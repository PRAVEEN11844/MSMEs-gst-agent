import { motion } from "framer-motion";
import SpendingChart from "@/components/SpendingChart";
import KPICard from "@/components/KPICard";
import { BarChart3, TrendingUp, Target, Zap } from "lucide-react";

const kpis = [
  { title: "Monthly Average", value: "₹14,387", change: "3%", trend: "down" as const, icon: BarChart3 },
  { title: "Highest Month", value: "₹18,500", change: "Dec", trend: "up" as const, icon: TrendingUp },
  { title: "Savings Rate", value: "24%", change: "2%", trend: "up" as const, icon: Target },
  { title: "Insights Found", value: "7", change: "New", trend: "up" as const, icon: Zap },
];

const Analytics = () => {
  return (
    <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h1 className="text-xl font-bold text-foreground">Analytics</h1>
        <p className="text-sm text-muted-foreground">Deep dive into your spending patterns</p>
      </motion.div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => (
          <KPICard key={kpi.title} {...kpi} index={i} />
        ))}
      </div>

      <SpendingChart />
    </div>
  );
};

export default Analytics;

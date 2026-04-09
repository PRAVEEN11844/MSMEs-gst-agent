import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";

interface Transaction {
  merchant: string;
  category: string;
  amount: string;
  date: string;
}

interface SpendingChartProps {
  transactions?: Transaction[];
}

const COLORS = [
  "hsl(224, 76%, 40%)",
  "hsl(160, 84%, 39%)",
  "hsl(38, 92%, 50%)",
  "hsl(280, 60%, 55%)",
  "hsl(0, 84%, 60%)",
  "hsl(190, 70%, 45%)",
  "hsl(330, 60%, 50%)",
  "hsl(50, 80%, 45%)",
];

function parseAmount(amountStr: string): number {
  const num = parseFloat(amountStr.replace(/[^0-9.\-]/g, ""));
  return isNaN(num) ? 0 : num;
}

function buildCategoryData(transactions: Transaction[]) {
  const categoryTotals: Record<string, number> = {};
  for (const tx of transactions) {
    const cat = tx.category || "Other";
    categoryTotals[cat] = (categoryTotals[cat] || 0) + parseAmount(tx.amount);
  }
  return Object.entries(categoryTotals)
    .map(([name, value]) => ({ name, value: Math.round(value) }))
    .sort((a, b) => b.value - a.value);
}

function buildMerchantData(transactions: Transaction[]) {
  const merchantTotals: Record<string, number> = {};
  for (const tx of transactions) {
    const m = tx.merchant || "Unknown";
    merchantTotals[m] = (merchantTotals[m] || 0) + parseAmount(tx.amount);
  }
  return Object.entries(merchantTotals)
    .map(([merchant, amount]) => ({ merchant, amount: Math.round(amount) }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 6);
}

function buildDateData(transactions: Transaction[]) {
  const dateTotals: Record<string, number> = {};
  for (const tx of transactions) {
    const d = tx.date || "Unknown";
    dateTotals[d] = (dateTotals[d] || 0) + parseAmount(tx.amount);
  }
  return Object.entries(dateTotals)
    .map(([date, amount]) => ({ date, amount: Math.round(amount) }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

// Static fallback data (shown only when no transactions uploaded)
const defaultLineData = [
  { date: "Sep", amount: 12400 },
  { date: "Oct", amount: 15800 },
  { date: "Nov", amount: 11200 },
  { date: "Dec", amount: 18500 },
  { date: "Jan", amount: 13900 },
  { date: "Feb", amount: 14520 },
];

const defaultPieData = [
  { name: "Shopping", value: 4890 },
  { name: "Food", value: 3200 },
  { name: "Utilities", value: 2100 },
  { name: "Transport", value: 1800 },
  { name: "Entertainment", value: 2530 },
];

const defaultBarData = [
  { merchant: "Amazon", amount: 4200 },
  { merchant: "Swiggy", amount: 2800 },
  { merchant: "Airtel", amount: 1600 },
  { merchant: "Netflix", amount: 1300 },
  { merchant: "Uber", amount: 1100 },
];

const SpendingChart = ({ transactions }: SpendingChartProps) => {
  const hasData = transactions && transactions.length > 0;

  const lineData = hasData ? buildDateData(transactions) : defaultLineData;
  const pieData = hasData ? buildCategoryData(transactions) : defaultPieData;
  const barData = hasData ? buildMerchantData(transactions) : defaultBarData;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Line chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-card rounded-xl shadow-soft border border-border p-5 lg:col-span-2"
      >
        <h3 className="font-semibold text-foreground text-sm mb-4">
          {hasData ? "Spending by Date" : "Monthly Spending Trend"}
        </h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={lineData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(214, 32%, 91%)" />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} />
            <YAxis tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(0, 0%, 100%)",
                border: "1px solid hsl(214, 32%, 91%)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [`₹${value.toLocaleString()}`, "Spent"]}
            />
            <Line
              type="monotone"
              dataKey="amount"
              stroke="hsl(224, 76%, 40%)"
              strokeWidth={2.5}
              dot={{ fill: "hsl(224, 76%, 40%)", r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Pie chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-card rounded-xl shadow-soft border border-border p-5"
      >
        <h3 className="font-semibold text-foreground text-sm mb-4">By Category</h3>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
              {pieData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(0, 0%, 100%)",
                border: "1px solid hsl(214, 32%, 91%)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [`₹${value.toLocaleString()}`]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap gap-3 mt-2">
          {pieData.map((item, i) => (
            <div key={item.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
              {item.name}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Bar chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="bg-card rounded-xl shadow-soft border border-border p-5"
      >
        <h3 className="font-semibold text-foreground text-sm mb-4">Top Merchants</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={barData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(214, 32%, 91%)" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} />
            <YAxis type="category" dataKey="merchant" tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} width={70} />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(0, 0%, 100%)",
                border: "1px solid hsl(214, 32%, 91%)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [`₹${value.toLocaleString()}`]}
            />
            <Bar dataKey="amount" fill="hsl(224, 76%, 40%)" radius={[0, 6, 6, 0]} barSize={20} />
          </BarChart>
        </ResponsiveContainer>
      </motion.div>
    </div>
  );
};

export default SpendingChart;

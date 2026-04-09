import { motion } from "framer-motion";
import TransactionsTable from "@/components/TransactionsTable";

const Transactions = () => {
  return (
    <div className="p-4 md:p-6 space-y-6 max-w-5xl mx-auto">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h1 className="text-xl font-bold text-foreground">Transactions</h1>
        <p className="text-sm text-muted-foreground">All extracted financial data</p>
      </motion.div>
      <TransactionsTable />
    </div>
  );
};

export default Transactions;

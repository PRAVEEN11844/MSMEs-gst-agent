import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Pencil, Download, Sparkles, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Transaction } from "@/lib/analyze-store";


interface TransactionsTableProps {
  transactions?: Transaction[];
  onUpdateTransaction?: (index: number, field: keyof Transaction, value: string) => void;
}

const TransactionsTable = ({ transactions, onUpdateTransaction }: TransactionsTableProps) => {
  const data = transactions && transactions.length > 0 ? transactions : [];
  const [editingCell, setEditingCell] = useState<{ row: number; field: string } | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = (rowIndex: number, field: string, currentValue: string) => {
    if (!onUpdateTransaction) return; // Only allow editing if handler provided
    setEditingCell({ row: rowIndex, field });
    setEditValue(currentValue);
  };

  const saveEdit = () => {
    if (editingCell && onUpdateTransaction) {
      onUpdateTransaction(editingCell.row, editingCell.field as keyof Transaction, editValue);
    }
    setEditingCell(null);
    setEditValue("");
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue("");
  };

  const isEditing = (rowIndex: number, field: string) =>
    editingCell?.row === rowIndex && editingCell?.field === field;

  const renderCell = (rowIndex: number, field: string, value: string, className: string) => {
    if (isEditing(rowIndex, field)) {
      return (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveEdit();
              if (e.key === "Escape") cancelEdit();
            }}
            className="bg-secondary rounded px-2 py-1 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20 w-full"
          />
          <button onClick={saveEdit} className="text-accent hover:text-accent/80 transition-colors shrink-0">
            <Save className="w-3 h-3" />
          </button>
          <button onClick={cancelEdit} className="text-muted-foreground hover:text-foreground transition-colors shrink-0">
            <X className="w-3 h-3" />
          </button>
        </div>
      );
    }
    return <span className={className}>{value}</span>;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-card rounded-xl shadow-soft border border-border overflow-hidden"
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <h3 className="font-semibold text-foreground">Extracted Transactions</h3>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-xs gap-1.5">
            <Download className="w-3.5 h-3.5" /> Export
          </Button>
          <Button size="sm" className="text-xs gap-1.5 gradient-primary text-primary-foreground">
            <Sparkles className="w-3.5 h-3.5" /> Ask AI
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-xs font-medium text-muted-foreground px-5 py-3">Status</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-5 py-3">Merchant</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-5 py-3">Category</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-5 py-3">Amount</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-5 py-3">Date</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.map((tx, i) => (
              <motion.tr
                key={tx.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="border-b border-border/50 last:border-0 hover:bg-secondary/50 transition-colors"
              >
                <td className="px-5 py-3.5">
                  {tx.status === "verified" ? (
                    <span className="w-5 h-5 rounded-full bg-accent/10 text-accent flex items-center justify-center">
                      <Check className="w-3 h-3" />
                    </span>
                  ) : (
                    <span className="w-5 h-5 rounded-full bg-warning/10 text-warning flex items-center justify-center text-[10px] font-bold">
                      ?
                    </span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-sm font-medium text-foreground">
                  {renderCell(i, "merchant", tx.merchant, "")}
                </td>
                <td className="px-5 py-3.5">
                  {isEditing(i, "category") ? (
                    renderCell(i, "category", tx.category, "")
                  ) : (
                    <span
                      className="text-xs bg-secondary text-secondary-foreground px-2 py-1 rounded-md cursor-pointer"
                      onClick={() => startEdit(i, "category", tx.category)}
                    >
                      {tx.category}
                    </span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-sm font-semibold text-foreground text-right tabular-nums">
                  {renderCell(i, "amount", tx.amount, "")}
                </td>
                <td className="px-5 py-3.5 text-xs text-muted-foreground text-right">{tx.date}</td>
                <td className="px-5 py-3.5 text-right">
                  <button
                    onClick={() => startEdit(i, "merchant", tx.merchant)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
};

export default TransactionsTable;

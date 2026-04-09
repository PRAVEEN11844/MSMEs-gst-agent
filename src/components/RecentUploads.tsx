import { motion } from "framer-motion";
import { FileText, Clock, CheckCircle } from "lucide-react";

const uploads = [
  { name: "Amazon Receipt", date: "2 hours ago", items: 3, status: "complete" },
  { name: "Electricity Bill", date: "Yesterday", items: 1, status: "complete" },
  { name: "Restaurant Bill", date: "3 days ago", items: 5, status: "complete" },
];

const RecentUploads = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="w-full max-w-2xl mx-auto mt-8"
    >
      <h3 className="text-sm font-semibold text-foreground mb-3">Recent Uploads</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {uploads.map((item, i) => (
          <motion.div
            key={item.name}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + i * 0.1 }}
            className="bg-card rounded-xl p-4 shadow-soft border border-border hover:shadow-elevated transition-shadow cursor-pointer group"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                <FileText className="w-4 h-4 text-primary" />
              </div>
              <CheckCircle className="w-4 h-4 text-accent ml-auto" />
            </div>
            <p className="text-sm font-medium text-foreground">{item.name}</p>
            <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              {item.date} · {item.items} items
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};

export default RecentUploads;

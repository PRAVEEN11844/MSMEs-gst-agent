import { useEffect } from "react";
import { motion } from "framer-motion";
import { Bell, Zap, ChevronRight, Loader2 } from "lucide-react";
import ReminderCard from "@/components/ReminderCard";
import { useReminderStore } from "@/lib/reminder-store";

const insights = [
  "Your food spending is 15% higher than last month",
  "You saved ₹800 on transport compared to January",
  "Consider switching to annual Netflix plan — saves ₹1,188/year",
];

const Reminders = () => {
  const { reminders, isLoadingReminders, fetchReminders, toggleReminder, deleteReminder } = useReminderStore();

  useEffect(() => {
    fetchReminders();
  }, []);

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-3xl mx-auto">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h1 className="text-xl font-bold text-foreground">Smart Reminders</h1>
        <p className="text-sm text-muted-foreground">AI-detected upcoming payments and insights</p>
      </motion.div>

      {/* Active Reminders */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Bell className="w-4 h-4 text-primary" /> Your Reminders
        </h2>

        {isLoadingReminders ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
            <span className="ml-2 text-sm text-muted-foreground">Loading reminders...</span>
          </div>
        ) : reminders.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-card rounded-xl p-8 shadow-soft border border-border text-center"
          >
            <Bell className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No active reminders yet.</p>
            <p className="text-xs text-muted-foreground mt-1">
              Upload a document to detect recurring payments and set reminders.
            </p>
          </motion.div>
        ) : (
          reminders.map((r, i) => (
            <ReminderCard
              key={r.id}
              merchant={r.merchant}
              amount={r.amount}
              nextDue={r.next_due_date}
              frequency={r.frequency_days}
              enabled={r.enabled}
              onToggle={() => toggleReminder(r.id)}
              onDelete={() => deleteReminder(r.id)}
              index={i}
            />
          ))
        )}
      </div>

      {/* Insights */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent" /> Smart Insights
        </h2>
        {insights.map((insight, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.1 }}
            className="bg-card rounded-xl p-4 shadow-soft border border-border flex items-center justify-between cursor-pointer hover:shadow-elevated transition-shadow"
          >
            <p className="text-sm text-foreground">{insight}</p>
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default Reminders;

import { useState } from "react";
import { motion } from "framer-motion";
import { Bell, CalendarClock, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SuggestionCardProps {
    merchant: string;
    amount: number;
    frequency: number;
    nextDue: string;
    onEnable: () => Promise<void>;
    index?: number;
}

const SuggestionCard = ({ merchant, amount, frequency, nextDue, onEnable, index = 0 }: SuggestionCardProps) => {
    const [enabling, setEnabling] = useState(false);
    const [enabled, setEnabled] = useState(false);

    const handleEnable = async () => {
        setEnabling(true);
        try {
            await onEnable();
            setEnabled(true);
        } catch (err) {
            console.error("Failed to enable reminder:", err);
        } finally {
            setEnabling(false);
        }
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString("en-IN", {
                month: "short",
                day: "numeric",
                year: "numeric",
            });
        } catch {
            return dateStr;
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-card rounded-xl p-4 shadow-soft border border-border flex items-center justify-between group hover:shadow-elevated transition-shadow"
        >
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <CalendarClock className="w-4 h-4 text-primary" />
                </div>
                <div>
                    <p className="text-sm font-medium text-foreground">{merchant}</p>
                    <p className="text-xs text-muted-foreground">
                        Every {frequency} days · ₹{amount.toLocaleString("en-IN")} · Due {formatDate(nextDue)}
                    </p>
                </div>
            </div>
            <div>
                {enabled ? (
                    <span className="flex items-center gap-1 text-xs text-accent font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Enabled
                    </span>
                ) : (
                    <Button
                        size="sm"
                        variant="outline"
                        className="text-xs gap-1.5"
                        onClick={handleEnable}
                        disabled={enabling}
                    >
                        <Bell className="w-3.5 h-3.5" />
                        {enabling ? "Enabling..." : "Set Reminder"}
                    </Button>
                )}
            </div>
        </motion.div>
    );
};

export default SuggestionCard;

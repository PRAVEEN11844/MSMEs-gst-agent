import { motion } from "framer-motion";
import { Bell, BellOff, Trash2, CalendarClock } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ReminderCardProps {
    merchant: string;
    amount: number;
    nextDue: string;
    frequency: number;
    enabled: boolean;
    onToggle: () => void;
    onDelete: () => void;
    index?: number;
}

const ReminderCard = ({
    merchant,
    amount,
    nextDue,
    frequency,
    enabled,
    onToggle,
    onDelete,
    index = 0,
}: ReminderCardProps) => {
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
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-card rounded-xl p-4 shadow-soft border border-border flex items-center justify-between group hover:shadow-elevated transition-shadow"
        >
            <div className="flex items-center gap-3">
                <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center ${enabled ? "bg-primary/10" : "bg-muted/30"
                        }`}
                >
                    {enabled ? (
                        <Bell className="w-4 h-4 text-primary" />
                    ) : (
                        <BellOff className="w-4 h-4 text-muted-foreground" />
                    )}
                </div>
                <div>
                    <p className="text-sm font-medium text-foreground">{merchant}</p>
                    <p className="text-xs text-muted-foreground">
                        Every {frequency} days · ₹{amount.toLocaleString("en-IN")}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <CalendarClock className="w-3 h-3" /> Due {formatDate(nextDue)}
                        </span>
                        <span
                            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${enabled
                                    ? "bg-accent/10 text-accent"
                                    : "bg-muted/30 text-muted-foreground"
                                }`}
                        >
                            {enabled ? "Active" : "Paused"}
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <Button
                    size="sm"
                    variant="outline"
                    className="text-xs gap-1"
                    onClick={onToggle}
                >
                    {enabled ? (
                        <>
                            <BellOff className="w-3 h-3" /> Pause
                        </>
                    ) : (
                        <>
                            <Bell className="w-3 h-3" /> Resume
                        </>
                    )}
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="text-xs text-destructive hover:bg-destructive/10"
                    onClick={onDelete}
                >
                    <Trash2 className="w-3 h-3" />
                </Button>
            </div>
        </motion.div>
    );
};

export default ReminderCard;

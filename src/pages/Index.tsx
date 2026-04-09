import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import RecentUploads from "@/components/RecentUploads";

const Index = () => {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="px-6 py-4 flex items-center justify-between border-b border-border md:hidden">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-semibold text-foreground text-lg">FinSight</span>
        </div>
      </header>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
            <Sparkles className="w-3 h-3" />
            AI-Powered Financial Intelligence
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-3">
            Understand your finances
            <br />
            <span className="text-gradient">in seconds</span>
          </h1>
          <p className="text-muted-foreground max-w-md mx-auto text-sm leading-relaxed">
            Upload receipts, bills, or screenshots. Our AI extracts, structures, and analyzes your spending — then answers your questions.
          </p>
        </motion.div>

        <UploadZone />
        <RecentUploads />
      </div>
    </div>
  );
};

export default Index;

import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileImage, FileText, Check, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/hooks/use-toast";
import { setAnalyzeResult, setAnalyzing, setAnalyzeError, fetchTransactions, setOcrConfidence } from "@/lib/analyze-store";
import { detectRecurring } from "@/lib/reminder-store";

type UploadState = "idle" | "hovering" | "uploading" | "processing" | "complete" | "error";

const UploadZone = () => {
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState("");
  const [ocrConfidence, setOcrConfidence] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const fileRef = useRef<File | null>(null);
  const navigate = useNavigate();

  const handleAnalyze = useCallback(async (file: File) => {
    setFileName(file.name);
    fileRef.current = file;
    setState("uploading");
    setProgress(0);
    setOcrConfidence(null);
    setErrorMessage("");
    setAnalyzing(true);

    // Simulate progress while uploading
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 5;
      });
    }, 150);

    try {
      const formData = new FormData();
      formData.append("file", file);

      setState("processing");
      setProgress(90);

      console.log("[UploadZone] Sending file to /api/analyze:", file.name);

      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      clearInterval(progressInterval);

      const raw = await response.text();
      let data: unknown = null;
      try {
        data = raw ? JSON.parse(raw) : null;
      } catch {
        data = null;
      }
      if (!response.ok || !data || typeof data !== "object") {
        const msg =
          (typeof data === "object" && data && "error" in data ? (data as { error?: string }).error : undefined) ||
          (raw && raw.length > 0 ? raw.slice(0, 200) : "Empty response from server") ||
          `HTTP ${response.status}`;
        throw new Error(msg);
      }
      const payload = data as {
        success?: boolean;
        data?: { ocr_confidence?: number; transactions?: unknown[]; fallback_used?: boolean };
        error?: string;
        fallback_used?: boolean;
      };
      console.log("[UploadZone] OCR Response:", payload);

      // Treat fallback_used as soft success — backend used OCR instead of Gemini
      const isFallback = payload.fallback_used || payload.data?.fallback_used;
      const hasData = payload.success || isFallback;

      if (!hasData || !payload.data) {
        throw new Error(payload.error ?? `Server error (${response.status})`);
      }

      setProgress(100);
      setState("complete");
      setOcrConfidence((payload.data.ocr_confidence as number) ?? null);

      if (isFallback) {
        toast({
          title: "⚠️ OCR Fallback Used",
          description: "Gemini AI was unavailable. Data extracted via OCR only — values marked 'pending', please verify.",
        });
      }

      // Fetch full transaction history from DB (merges new + old)
      await fetchTransactions();

      // Auto-detect recurring payments from extracted transactions
      if (Array.isArray(payload.data.transactions) && payload.data.transactions.length > 1) {
        detectRecurring(payload.data.transactions as { merchant: string; amount: string; date: string }[]);
      }

    } catch (err) {
      clearInterval(progressInterval);
      const message = err instanceof Error ? err.message : "Failed to analyze document.";
      console.error("[UploadZone] Error:", message);
      setState("error");
      setErrorMessage(message);
      setAnalyzeError(message);
      toast({
        title: "Analysis Failed",
        description: message,
        variant: "destructive",
      });
    }
  }, []);

  const handleRetry = useCallback(() => {
    if (fileRef.current) {
      handleAnalyze(fileRef.current);
    }
  }, [handleAnalyze]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setState("idle");
      const file = e.dataTransfer.files[0];
      if (file) handleAnalyze(file);
    },
    [handleAnalyze]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleAnalyze(file);
    },
    [handleAnalyze]
  );

  const reset = () => {
    setState("idle");
    setProgress(0);
    setFileName("");
    setOcrConfidence(null);
    setErrorMessage("");
    fileRef.current = null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="w-full max-w-2xl mx-auto"
    >
      <AnimatePresence mode="wait">
        {(state === "idle" || state === "hovering") && (
          <motion.label
            key="upload"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            onDragOver={(e) => {
              e.preventDefault();
              setState("hovering");
            }}
            onDragLeave={() => setState("idle")}
            onDrop={handleDrop}
            className={`relative flex flex-col items-center justify-center gap-4 p-12 rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-300 ${state === "hovering"
              ? "border-primary bg-primary/5 scale-[1.02]"
              : "border-border hover:border-primary/50 hover:bg-secondary/50"
              }`}
          >
            <input
              type="file"
              accept="image/*,.pdf"
              onChange={handleFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
            <motion.div
              animate={state === "hovering" ? { scale: 1.1, y: -4 } : { scale: 1, y: 0 }}
              className="w-16 h-16 rounded-2xl gradient-primary flex items-center justify-center shadow-elevated"
            >
              <Upload className="w-7 h-7 text-primary-foreground" />
            </motion.div>
            <div className="text-center">
              <p className="text-lg font-semibold text-foreground">
                Drop your financial document here
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                or click to browse · PNG, JPG, PDF supported
              </p>
            </div>
            <div className="flex items-center gap-3 mt-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <FileImage className="w-4 h-4" /> Images
              </div>
              <div className="w-px h-4 bg-border" />
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <FileText className="w-4 h-4" /> PDFs
              </div>
            </div>
          </motion.label>
        )}

        {(state === "uploading" || state === "processing" || state === "complete" || state === "error") && (
          <motion.div
            key="progress"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="p-8 rounded-2xl bg-card shadow-soft border border-border"
          >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center ${state === "complete" ? "gradient-accent" : state === "error" ? "bg-destructive/10" : "gradient-primary"
                    }`}
                >
                  {state === "complete" ? (
                    <Check className="w-5 h-5 text-accent-foreground" />
                  ) : state === "error" ? (
                    <X className="w-5 h-5 text-destructive" />
                  ) : (
                    <Loader2 className="w-5 h-5 text-primary-foreground animate-spin" />
                  )}
                </div>
                <div>
                  <p className="font-semibold text-foreground text-sm">{fileName}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {state === "uploading" && "Uploading document..."}
                    {state === "processing" && "Extracting text with AI OCR..."}
                    {state === "complete" &&
                      `Analysis complete · ${ocrConfidence !== null ? Math.round(ocrConfidence * 100) : 94}% confidence`}
                    {state === "error" && (errorMessage || "Upload failed")}
                  </p>
                </div>
              </div>
              <button onClick={reset} className="text-muted-foreground hover:text-foreground transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <Progress value={state === "complete" ? 100 : state === "processing" ? 100 : progress} className="h-1.5" />

            {state === "complete" && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3 mt-6"
              >
                <Button className="gradient-primary text-primary-foreground" onClick={() => navigate("/dashboard")}>
                  View Results
                </Button>
                <Button variant="outline" onClick={reset}>
                  Upload Another
                </Button>
              </motion.div>
            )}

            {state === "error" && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3 mt-6"
              >
                <Button className="gradient-primary text-primary-foreground" onClick={handleRetry}>
                  Retry
                </Button>
                <Button variant="outline" onClick={reset}>
                  Upload Different File
                </Button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default UploadZone;

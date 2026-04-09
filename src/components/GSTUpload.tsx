import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileImage, FileText, Check, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/hooks/use-toast";
import { setGSTAnalyzing, setGSTError, fetchGSTInvoices, fetchGSTSummary } from "@/lib/gst-store";

type UploadState = "idle" | "hovering" | "uploading" | "processing" | "complete" | "error";

const GSTUpload = () => {
    const [state, setState] = useState<UploadState>("idle");
    const [progress, setProgress] = useState(0);
    const [fileName, setFileName] = useState("");
    const [ocrConfidence, setOcrConfidence] = useState<number | null>(null);
    const [errorMessage, setErrorMessage] = useState("");
    const fileRef = useRef<File | null>(null);

    const handleAnalyze = useCallback(async (file: File) => {
        setFileName(file.name);
        fileRef.current = file;
        setState("uploading");
        setProgress(0);
        setOcrConfidence(null);
        setErrorMessage("");
        setGSTAnalyzing(true);

        const progressInterval = setInterval(() => {
            setProgress((prev) => (prev >= 90 ? 90 : prev + 5));
        }, 150);

        try {
            const formData = new FormData();
            formData.append("file", file);

            setState("processing");
            setProgress(90);

            const response = await fetch("/api/gst/analyze", {
                method: "POST",
                body: formData,
            });

            clearInterval(progressInterval);

            const data = await response.json();

            if (!response.ok || data.status !== "success") {
                throw new Error(data.message || data.error || "Analysis failed");
            }

            setProgress(100);
            setState("complete");
            setOcrConfidence(data.invoice.ocr_confidence);

            if (data.invoice.tax_inferred) {
                toast({
                    title: "Tax Inferred",
                    description: "Tax totals weren't explicit so they were mathematically inferred from the total.",
                });
            } else if (data.invoice.tax_warning) {
                toast({
                    title: "GST Computation Warning",
                    description: "The sum of taxes and taxable value doesn't exactly match the total amount. Please verify.",
                    variant: "destructive",
                });
            }

            // Refresh data
            await fetchGSTInvoices();
            await fetchGSTSummary();
            setGSTAnalyzing(false);

        } catch (err) {
            clearInterval(progressInterval);
            const message = err instanceof Error ? err.message : "Failed to analyze GST document.";
            setState("error");
            setErrorMessage(message);
            setGSTError(message);
            toast({
                title: "GST Extraction Failed",
                description: message,
                variant: "destructive",
            });
        }
    }, []);

    const handleRetry = () => {
        if (fileRef.current) handleAnalyze(fileRef.current);
    };

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setState("idle");
            const file = e.dataTransfer.files[0];
            if (file) handleAnalyze(file);
        },
        [handleAnalyze]
    );

    return (
        <div className="w-full max-w-2xl mx-auto mt-8">
            <div
                onDragOver={(e) => {
                    e.preventDefault();
                    if (state === "idle") setState("hovering");
                }}
                onDragLeave={() => {
                    if (state === "hovering") setState("idle");
                }}
                onDrop={handleDrop}
                className={`relative overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 ease-out 
          ${state === "hovering" ? "border-primary bg-primary/5 scale-[1.02]" : "border-border bg-card hover:border-primary/50"}
          ${(state === "uploading" || state === "processing") && "pointer-events-none"}`}
            >
                <div className="p-12 flex flex-col items-center justify-center min-h-[300px] text-center">
                    <AnimatePresence mode="wait">
                        {state === "idle" || state === "hovering" ? (
                            <motion.div
                                key="idle"
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="flex flex-col items-center"
                            >
                                <div className="p-4 rounded-full bg-primary/10 mb-6 group-hover:bg-primary/20 transition-colors">
                                    <Upload className="w-8 h-8 text-primary" />
                                </div>
                                <h3 className="text-xl font-semibold mb-2">Drop your MSME GST Invoice</h3>
                                <p className="text-muted-foreground mb-6 max-w-xs focus:ring-1 focus:ring-ring focus:outline-none">
                                    Supports clear images of GSTR invoices (JPEG, PNG)
                                </p>
                                <label className="relative cursor-pointer">
                                    <Button variant="secondary" className="pointer-events-none relative z-10 w-48 focus:ring-1 focus:ring-ring focus:outline-none">Select File</Button>
                                    <input
                                        type="file"
                                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                                        accept="image/*,.pdf"
                                        onChange={(e) => {
                                            const file = e.target.files?.[0];
                                            if (file) handleAnalyze(file);
                                        }}
                                    />
                                </label>
                            </motion.div>
                        ) : state === "error" ? (
                            <motion.div key="error" className="flex flex-col items-center">
                                <div className="p-4 rounded-full bg-destructive/10 mb-6">
                                    <X className="w-8 h-8 text-destructive" />
                                </div>
                                <h3 className="text-xl font-semibold mb-2 text-destructive">Extraction Failed</h3>
                                <p className="text-muted-foreground mb-6 max-w-sm">{errorMessage}</p>
                                <div className="flex gap-4">
                                    <Button variant="outline" onClick={() => setState("idle")}>Cancel</Button>
                                    <Button onClick={handleRetry}>Try Again</Button>
                                </div>
                            </motion.div>
                        ) : (
                            <motion.div key="progress" className="w-full max-w-md mx-auto">
                                <div className="flex items-center gap-4 mb-6">
                                    <div className="p-3 bg-secondary rounded-lg">
                                        {fileName.endsWith(".pdf") ? <FileText className="w-6 h-6" /> : <FileImage className="w-6 h-6" />}
                                    </div>
                                    <div className="flex-1 text-left overflow-hidden">
                                        <p className="font-medium truncate">{fileName}</p>
                                        <p className="text-sm text-muted-foreground">
                                            {state === "uploading" && "Uploading to secure server..."}
                                            {state === "processing" && "Extracting GST values with Gemini 2.5..."}
                                            {state === "complete" && "Extraction complete!"}
                                        </p>
                                    </div>
                                    {state === "complete" ? (
                                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="p-2 bg-green-500/20 text-green-500 rounded-full">
                                            <Check className="w-5 h-5" />
                                        </motion.div>
                                    ) : (
                                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                                    )}
                                </div>
                                <Progress value={progress} className="h-2" />
                                {ocrConfidence && (
                                    <p className="text-sm mt-4 text-center text-muted-foreground">
                                        Confidence: {(ocrConfidence * 100).toFixed(1)}%
                                    </p>
                                )}
                                {state === "complete" && (
                                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 flex justify-center">
                                        <Button onClick={() => setState("idle")}>Upload Another</Button>
                                    </motion.div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
};

export default GSTUpload;

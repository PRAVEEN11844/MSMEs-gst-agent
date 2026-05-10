import { useSyncExternalStore, useCallback } from "react";

export interface Transaction {
    id: number;
    merchant: string;
    category: string;
    amount: string;
    date: string;
    status: "verified" | "pending";
}

interface AnalyzeState {
    transactions: Transaction[];
    ocrConfidence: number | null;
    isAnalyzing: boolean;
    error: string | null;
}

let state: AnalyzeState = {
    transactions: [],
    ocrConfidence: null,
    isAnalyzing: false,
    error: null,
};

const listeners = new Set<() => void>();

function emitChange() {
    listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
}

function getSnapshot() {
    return state;
}

// --- Actions ---

export function setAnalyzeResult(transactions: Transaction[], ocrConfidence: number) {
    state = { ...state, transactions, ocrConfidence, isAnalyzing: false, error: null };
    emitChange();
}

export function setOcrConfidence(confidence: number) {
    state = { ...state, ocrConfidence: confidence };
    emitChange();
}

export function setAnalyzing(isAnalyzing: boolean) {
    state = { ...state, isAnalyzing, error: null };
    emitChange();
}

export function setAnalyzeError(error: string) {
    state = { ...state, error, isAnalyzing: false };
    emitChange();
}

export function updateTransaction(index: number, field: keyof Transaction, value: string) {
    const updated = [...state.transactions];
    if (updated[index]) {
        updated[index] = { ...updated[index], [field]: value };
        state = { ...state, transactions: updated };
        emitChange();
    }
}

export function clearAnalyzeState() {
    state = { transactions: [], ocrConfidence: null, isAnalyzing: false, error: null };
    emitChange();
}

export async function fetchTransactions() {
    try {
        const res = await fetch("/api/transactions");
        const data = await res.json();
        // Backend returns: { success, data: { transactions: [...] }, error }
        if (!data.success && data.error) {
            console.error("[AnalyzeStore] Server error fetching transactions:", data.error);
            return;
        }
        const transactions = data?.data?.transactions ?? [];
        if (transactions.length > 0) {
            // Assign IDs if not present
            const txns = transactions.map((tx: Transaction, i: number) => ({
                ...tx,
                id: tx.id ?? i + 1,
                status: tx.status ?? "verified",
            }));
            state = { ...state, transactions: txns, ocrConfidence: state.ocrConfidence };
            emitChange();
            console.log(`[AnalyzeStore] Loaded ${txns.length} transactions from DB`);
        }
    } catch (err) {
        console.error("[AnalyzeStore] Failed to fetch transactions:", err);
    }
}

// --- Hook ---

export function useAnalyzeStore() {
    const snapshot = useSyncExternalStore(subscribe, getSnapshot);

    const update = useCallback(
        (index: number, field: keyof Transaction, value: string) => {
            updateTransaction(index, field, value);
        },
        []
    );

    return {
        ...snapshot,
        updateTransaction: update,
        setAnalyzeResult,
        setAnalyzing,
        setAnalyzeError,
        clearAnalyzeState,
        fetchTransactions,
    };
}

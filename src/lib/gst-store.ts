import { useSyncExternalStore, useCallback } from "react";

export interface GSTInvoice {
    id?: string;
    gstin: string;
    invoice_number: string;
    invoice_date: string;
    taxable_value: number;
    cgst: number;
    sgst: number;
    igst: number;
    total_amount: number;
    ocr_confidence: number;
    tax_warning: boolean;
    tax_inferred?: boolean;
    tax_breakdown_explicit?: boolean;
    tax_rates_found?: number[];
    created_at?: string;
}

export interface GSTSummary {
    total_revenue: number;
    total_cgst: number;
    total_sgst: number;
    total_igst: number;
    total_gst_liability: number;
    invoice_count: number;
}

interface GSTState {
    invoices: GSTInvoice[];
    summary: GSTSummary | null;
    isAnalyzing: boolean;
    error: string | null;
}

let state: GSTState = {
    invoices: [],
    summary: null,
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

export function setGSTAnalyzing(isAnalyzing: boolean) {
    state = { ...state, isAnalyzing, error: null };
    emitChange();
}

export function setGSTError(error: string) {
    state = { ...state, error, isAnalyzing: false };
    emitChange();
}

export async function fetchGSTInvoices() {
    try {
        const res = await fetch("/api/gst/invoices");
        const json = await res.json();
        
        if (json.success && json.data) {
            state = { ...state, invoices: json.data };
            emitChange();
        } else if (!json.success && json.error) {
            console.error("[GSTStore] Server error fetching invoices:", json.error);
        }
    } catch (err) {
        console.error("[GSTStore] Failed to fetch invoices:", err);
    }
}

export async function fetchGSTSummary() {
    try {
        const res = await fetch("/api/gst/summary/monthly");
        const json = await res.json();
        if (json.success && json.data && typeof json.data.total_revenue === 'number') {
            state = { ...state, summary: json.data as GSTSummary };
            emitChange();
        } else if (!json.success && json.error) {
            console.error("[GSTStore] Server error fetching summary:", json.error);
        }
    } catch (err) {
        console.error("[GSTStore] Failed to fetch summary:", err);
    }
}

// --- Hook ---

export function useGSTStore() {
    const snapshot = useSyncExternalStore(subscribe, getSnapshot);
    return {
        ...snapshot,
        setGSTAnalyzing,
        setGSTError,
        fetchGSTInvoices,
        fetchGSTSummary,
    };
}

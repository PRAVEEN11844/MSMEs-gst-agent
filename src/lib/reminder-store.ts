import { useSyncExternalStore, useCallback } from "react";

// --------------- Types ---------------

export interface RecurringPayment {
    merchant: string;
    average_amount: number;
    frequency_days: number;
    last_date: string;
    next_due_date: string;
}

export interface Reminder {
    id: string;
    merchant: string;
    amount: number;
    frequency_days: number;
    next_due_date: string;
    enabled: boolean;
    created_at: string;
}

// --------------- State ---------------

interface ReminderState {
    recurringPayments: RecurringPayment[];
    reminders: Reminder[];
    isDetecting: boolean;
    isLoadingReminders: boolean;
}

let state: ReminderState = {
    recurringPayments: [],
    reminders: [],
    isDetecting: false,
    isLoadingReminders: false,
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

// --------------- Actions ---------------

export async function detectRecurring(transactions: { merchant: string; amount: string; date: string }[]) {
    state = { ...state, isDetecting: true };
    emitChange();
    try {
        const res = await fetch("/api/detect-recurring", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transactions }),
        });
        const data = await res.json();
        // Backend returns: { success, data: { recurring: [...] }, error }
        const recurring = data?.data?.recurring ?? data?.recurring ?? [];
        state = { ...state, recurringPayments: recurring, isDetecting: false };
        emitChange();
    } catch (err) {
        console.error("[ReminderStore] detectRecurring error:", err);
        state = { ...state, isDetecting: false };
        emitChange();
    }
}

export async function fetchReminders() {
    state = { ...state, isLoadingReminders: true };
    emitChange();
    try {
        const res = await fetch("/api/reminders");
        const data = await res.json();
        // Backend returns: { success, data: { reminders: [...] }, error }
        const reminders = data?.data?.reminders ?? data?.reminders ?? [];
        state = { ...state, reminders, isLoadingReminders: false };
        emitChange();
    } catch (err) {
        console.error("[ReminderStore] fetchReminders error:", err);
        state = { ...state, isLoadingReminders: false };
        emitChange();
    }
}

export async function createReminder(item: RecurringPayment) {
    try {
        await fetch("/api/reminders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                merchant: item.merchant,
                amount: item.average_amount,
                frequency_days: item.frequency_days,
                next_due_date: item.next_due_date,
            }),
        });
        await fetchReminders();
    } catch (err) {
        console.error("[ReminderStore] createReminder error:", err);
    }
}

export async function toggleReminder(id: string) {
    try {
        await fetch(`/api/reminders/${id}`, { method: "PATCH" });
        await fetchReminders();
    } catch (err) {
        console.error("[ReminderStore] toggleReminder error:", err);
    }
}

export async function deleteReminder(id: string) {
    try {
        await fetch(`/api/reminders/${id}`, { method: "DELETE" });
        await fetchReminders();
    } catch (err) {
        console.error("[ReminderStore] deleteReminder error:", err);
    }
}

// --------------- Hook ---------------

export function useReminderStore() {
    const snapshot = useSyncExternalStore(subscribe, getSnapshot);

    return {
        ...snapshot,
        detectRecurring,
        fetchReminders,
        createReminder,
        toggleReminder,
        deleteReminder,
    };
}

// RAG Chat — routes all questions through backend /api/ask endpoint
// which grounds answers in uploaded transaction data

export async function sendMessageToGemini(message: string): Promise<string> {
    console.log(`[Chat] Sending question to /api/ask: "${message.substring(0, 80)}..."`);

    const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: message }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.answer || `Server error: ${response.status}`);
    }

    const data = await response.json();
    console.log(`[Chat] Received answer (${data.answer?.length || 0} chars)`);
    return data.answer;
}

export function resetChat(): void {
    console.log("[Chat] Chat session reset");
}

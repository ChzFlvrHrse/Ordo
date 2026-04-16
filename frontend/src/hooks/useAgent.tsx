import { useState, useCallback } from "react";
import config from "../config";

export interface Message {
    role: "user" | "assistant";
    content: string;
}

export function useAgent(onBooking?: () => void) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const sendMessage = useCallback(async (text: string) => {
        const userMessage: Message = { role: "user", content: text };
        const updatedMessages = [...messages, userMessage];
        setMessages(updatedMessages);
        setLoading(true);
        setError(null);

        try {
            const res = await fetch(`${config.apiBaseUrl}/agent/chat`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": config.apiKey,
                },
                body: JSON.stringify({
                    user_id: config.userId,
                    messages: updatedMessages,
                }),
            });

            const data = await res.json();
            if (!data.success) throw new Error(data.error || "Agent error");

            const assistantMessage: Message = {
                role: "assistant",
                content: data.message,
            };

            setMessages(data.messages.filter((m: any) =>
                typeof m.content === "string"
            ));

            // Trigger calendar refetch if agent likely made a booking change
            const lower = data.message.toLowerCase();
            if (onBooking && (lower.includes("booked") || lower.includes("cancelled") || lower.includes("rescheduled"))) {
                onBooking();
            }

        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [messages, onBooking]);

    const clearMessages = useCallback(() => setMessages([]), []);

    return { messages, loading, error, sendMessage, clearMessages };
}

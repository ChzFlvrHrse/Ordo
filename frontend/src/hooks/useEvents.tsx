import { useState, useEffect, useCallback } from "react";
import config from "../config";

export interface OrdoEvent {
    id: string;
    title: string;
    start: string;
    end: string;
    provider: "google" | "outlook" | "ordo";
    location?: string;
    description?: string;
    attendees?: string[];
}

function normalizeGoogleEvent(event: any): OrdoEvent {
    return {
        id: event.id,
        title: event.summary || "(No title)",
        start: event.start?.dateTime || event.start?.date,
        end: event.end?.dateTime || event.end?.date,
        provider: "google",
        location: event.location,
        description: event.description,
        attendees: event.attendees?.map((a: any) => a.email),
    };
}

export function useEvents() {
    const [events, setEvents] = useState<OrdoEvent[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchEvents = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(
                `${config.apiBaseUrl}/google_calendar/events?user_id=${config.userId}`,
                { headers: { "X-API-Key": config.apiKey } }
            );
            const data = await res.json();
            if (!data.success) throw new Error(data.error || "Failed to fetch events");
            setEvents(data.events.map(normalizeGoogleEvent));
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchEvents();
    }, [fetchEvents]);

    return { events, loading, error, refetch: fetchEvents };
}

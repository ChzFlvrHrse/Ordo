import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import config from "../config";

export interface OrdoEvent {
    id: string;
    title: string;
    start: string;
    end: string;
    provider: "google" | "outlook" | "ordo";
    email?: string;
    label?: string;
    color?: string;
    location?: string;
    description?: string;
    attendees?: string[];
}

function normalizeGoogleEvent(event: any, integrations: any[]): OrdoEvent {
    const account = event._ordo_account;
    const integration = integrations.find(i => i.email === account);
    return {
        id: event.id,
        title: event.summary || "(No title)",
        start: event.start?.dateTime || event.start?.date,
        end: event.end?.dateTime || event.end?.date,
        provider: "google",
        email: account,
        label: integration?.label,
        color: integration?.color || "#22d3ee",
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
            // Pretty cool, fetches and checks in parallel, and sets the events
            const [statusRes, eventsRes] = await Promise.all([
                fetch(`${config.apiBaseUrl}/google_calendar/status?user_id=${config.userId}`,
                    { headers: { "X-API-Key": config.apiKey } }),
                fetch(`${config.apiBaseUrl}/google_calendar/events?user_id=${config.userId}`,
                    { headers: { "X-API-Key": config.apiKey } }),
            ]);

            if (eventsRes.status === 404) {
                setEvents([]);
                return;
            }

            const statusData = await statusRes.json();
            const eventsData = await eventsRes.json();

            if (!eventsData.success) throw new Error(eventsData.error || "Failed to fetch events");

            const integrations = statusData.integrations || [];
            setEvents(eventsData.events.map((e: any) => normalizeGoogleEvent(e, integrations)));

        } catch (e: any) {
            setError(e.message);
            toast.error(e.message || "Failed to load events");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchEvents();
    }, [fetchEvents]);

    return { events, loading, error, refetch: fetchEvents };
}

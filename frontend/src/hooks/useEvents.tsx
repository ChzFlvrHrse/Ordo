import { useState, useEffect, useCallback, useMemo } from "react";
import toast from "react-hot-toast";
import config from "../config";

export interface OrdoEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  provider: "google" | "microsoft" | "ordo";
  email?: string;
  label?: string;
  color?: string;
  location?: string;
  description?: string;
  attendees?: string[];
  meetLink?: string;
  htmlLink?: string;
}

function normalizeGoogleEvent(event: any, integrations: any[]): OrdoEvent {
  const account = event._ordo_account;
  const integration = integrations.find(
    (i) => i.provider === "google" && i.email === account
  );

  const meetLink =
    event.conferenceData?.entryPoints?.find((e: any) => e.entryPointType === "video")?.uri ||
    null;

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
    meetLink,
    htmlLink: event.htmlLink,
  };
}

function normalizeMicrosoftEvent(event: any, integrations: any[]): OrdoEvent {
  const account = event._ordo_account;
  const integration = integrations.find(
    (i) => i.provider === "microsoft" && i.email === account
  );

  return {
    id: event.id,
    title: event.subject || "(No title)",
    start: event.start?.dateTime,
    end: event.end?.dateTime,
    provider: "microsoft",
    email: account,
    label: integration?.label,
    color: integration?.color || "#2563eb",
    location: event.location?.displayName,
    description: event.bodyPreview,
    attendees: event.attendees?.map((a: any) => a.emailAddress?.address).filter(Boolean),
    meetLink: event.onlineMeeting?.joinUrl || null,
    htmlLink: event.webLink,
  };
}

function getMonthKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthBounds(monthKey: string) {
  const [yearStr, monthStr] = monthKey.split("-");
  const year = Number(yearStr);
  const monthIndex = Number(monthStr) - 1;

  const start = new Date(Date.UTC(year, monthIndex, 1, 0, 0, 0, 0));
  const end = new Date(Date.UTC(year, monthIndex + 1, 1, 0, 0, 0, 0));

  return { start, end };
}

function getMonthsInRange(start: Date, end: Date) {
  const months: string[] = [];
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  const last = new Date(end.getFullYear(), end.getMonth(), 1);

  while (cursor <= last) {
    months.push(getMonthKey(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }

  return months;
}

function dedupeEvents(events: OrdoEvent[]) {
  const map = new Map<string, OrdoEvent>();

  for (const event of events) {
    const key = `${event.provider}:${event.email || "unknown"}:${event.id}`;
    if (!map.has(key)) {
      map.set(key, event);
    }
  }

  return Array.from(map.values()).sort((a, b) => {
    const aStart = a.start || "";
    const bStart = b.start || "";
    return aStart.localeCompare(bStart);
  });
}

export function useEvents({
  visibleStart,
  visibleEnd,
}: {
  visibleStart: Date | null;
  visibleEnd: Date | null;
}) {
  const [monthCache, setMonthCache] = useState<Record<string, OrdoEvent[]>>({});
  const [loadingMonths, setLoadingMonths] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<any[]>([]);

  const loadStatus = useCallback(async () => {
    const headers = { "X-API-Key": config.apiKey };
    const [googleRes, microsoftRes] = await Promise.all([
      fetch(`${config.apiBaseUrl}/google_calendar/status?user_id=${config.userId}`, { headers }),
      fetch(`${config.apiBaseUrl}/microsoft_calendar/status?user_id=${config.userId}`, { headers }),
    ]);

    const [googleData, microsoftData] = await Promise.all([
      googleRes.ok ? googleRes.json() : Promise.resolve({ integrations: [] }),
      microsoftRes.ok ? microsoftRes.json() : Promise.resolve({ integrations: [] }),
    ]);

    const google = (googleData.integrations || []).map((i: any) => ({ ...i, provider: "google" }));
    const microsoft = (microsoftData.integrations || []).map((i: any) => ({ ...i, provider: "microsoft" }));
    return [...google, ...microsoft];
  }, []);

  const fetchProviderEvents = useCallback(
    async (provider: "google" | "microsoft", start: Date, end: Date) => {
      const base = provider === "google" ? "google_calendar" : "microsoft_calendar";
      const res = await fetch(
        `${config.apiBaseUrl}/${base}/events?user_id=${config.userId}&start=${encodeURIComponent(
          start.toISOString()
        )}&end=${encodeURIComponent(end.toISOString())}`,
        { headers: { "X-API-Key": config.apiKey } }
      );

      // 404 = no integration of this provider — that's fine, not an error.
      if (res.status === 404) return [];

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || `Failed to fetch ${provider} events`);
      }
      return data.events || [];
    },
    []
  );

  const fetchMonth = useCallback(
    async (monthKey: string) => {
      setLoadingMonths((prev) => (prev.includes(monthKey) ? prev : [...prev, monthKey]));
      setError(null);

      try {
        const { start, end } = getMonthBounds(monthKey);

        const [statusData, googleEvents, microsoftEvents] = await Promise.all([
          loadStatus(),
          fetchProviderEvents("google", start, end),
          fetchProviderEvents("microsoft", start, end),
        ]);

        const normalized: OrdoEvent[] = [
          ...googleEvents.map((e: any) => normalizeGoogleEvent(e, statusData)),
          ...microsoftEvents.map((e: any) => normalizeMicrosoftEvent(e, statusData)),
        ];

        setIntegrations(statusData);
        setMonthCache((prev) => ({
          ...prev,
          [monthKey]: normalized,
        }));
      } catch (e: any) {
        setError(e.message);
        toast.error(e.message || "Failed to load events");
      } finally {
        setLoadingMonths((prev) => prev.filter((m) => m !== monthKey));
      }
    },
    [loadStatus, fetchProviderEvents]
  );

  const ensureMonthsLoaded = useCallback(
    async (start: Date | null, end: Date | null) => {
      if (!start || !end) return;

      const neededMonths = getMonthsInRange(start, new Date(end.getTime() - 1));
      const missing = neededMonths.filter(
        (monthKey) => !monthCache[monthKey] && !loadingMonths.includes(monthKey)
      );

      if (missing.length === 0) return;

      await Promise.all(missing.map((monthKey) => fetchMonth(monthKey)));
    },
    [monthCache, loadingMonths, fetchMonth]
  );

  useEffect(() => {
    ensureMonthsLoaded(visibleStart, visibleEnd);
  }, [visibleStart, visibleEnd, ensureMonthsLoaded]);

  const events = useMemo(() => {
    if (!visibleStart || !visibleEnd) return [];

    const months = getMonthsInRange(visibleStart, new Date(visibleEnd.getTime() - 1));
    const merged = months.flatMap((monthKey) => monthCache[monthKey] || []);

    return dedupeEvents(merged);
  }, [visibleStart, visibleEnd, monthCache]);

  const loading = loadingMonths.length > 0;

  const refetch = useCallback(async () => {
    if (!visibleStart || !visibleEnd) return;

    const months = getMonthsInRange(visibleStart, new Date(visibleEnd.getTime() - 1));

    setMonthCache((prev) => {
      const next = { ...prev };
      for (const month of months) {
        delete next[month];
      }
      return next;
    });

    await Promise.all(months.map((monthKey) => fetchMonth(monthKey)));
  }, [visibleStart, visibleEnd, fetchMonth]);

  return {
    events,
    integrations,
    loading,
    error,
    refetch,
    ensureMonthsLoaded,
  };
}

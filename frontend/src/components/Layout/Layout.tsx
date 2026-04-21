import React, { useState, useCallback, useEffect } from "react";
import Calendar from "../Calendar/Calendar";
import AgentChat from "../AgentChat/AgentChat";
import { useEvents } from "../../hooks/useEvents";
import { useAgent } from "../../hooks/useAgent";
import config from "../../config";
import toast from "react-hot-toast";
import "./Layout.css";

export default function Layout() {
  const [activeCalendars, setActiveCalendars] = useState<any[]>([]);
  const [dragging, setDragging] = useState(false);
  const [date, setDate] = useState(new Date());
  const [visibleRange, setVisibleRange] = useState<{ start: Date; end: Date } | null>(null);

  const updateVisibleRange = useCallback((next: { start: Date; end: Date }) => {
    setVisibleRange((prev) => {
      if (
        prev &&
        prev.start.getTime() === next.start.getTime() &&
        prev.end.getTime() === next.end.getTime()
      ) {
        return prev;
      }
      return next;
    });
  }, []);

  const {
    events,
    loading: eventsLoading,
    refetch,
    ensureMonthsLoaded,
  } = useEvents({
    visibleStart: visibleRange?.start ?? null,
    visibleEnd: visibleRange?.end ?? null,
  });

  const { messages, loading: agentLoading, error, sendMessage } = useAgent(refetch);

  const onMouseDown = useCallback(() => setDragging(true), []);
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
  }, [dragging]);
  const onMouseUp = useCallback(() => setDragging(false), []);

  const fetchActiveCalendars = useCallback(async () => {
    try {
      const result = await fetch(
        `${config.apiBaseUrl}/integrations/calendars?user_id=${config.userId}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": config.apiKey,
          },
        }
      );

      if (!result.ok) {
        return;
      }

      const data = await result.json();
      setActiveCalendars(data.calendars ?? []);
    } catch (error) {
      toast.error("Could not load calendar connections");
      setActiveCalendars([]);
    }
  }, []);

  useEffect(() => {
    fetchActiveCalendars();
  }, [fetchActiveCalendars]);

  const handleCalendarRefetch = useCallback(async () => {
    await Promise.all([fetchActiveCalendars(), refetch()]);
  }, [fetchActiveCalendars, refetch]);

  return (
    <div
      className={`layout${dragging ? " layout--dragging" : ""}`}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      <div className="layout-inner">
        <div className="layout-calendar">
          <Calendar
            events={events}
            loading={eventsLoading}
            activeCalendars={activeCalendars}
            date={date}
            setDate={setDate}
            setVisibleRange={updateVisibleRange}
            ensureMonthsLoaded={ensureMonthsLoaded}
            refetch={handleCalendarRefetch}
          />
        </div>

        <div className="layout-divider" onMouseDown={onMouseDown}>
          <div className="divider-handle" />
        </div>

        <div className="layout-agent">
          <AgentChat
            messages={messages}
            loading={agentLoading}
            error={error}
            onSend={sendMessage}
          />
        </div>
      </div>
    </div>
  );
}

import React, { useState, useCallback, useEffect } from "react";
import { CalendarDays, Grid2x2, PieChart, Mail, Briefcase, Settings, LogOut } from "lucide-react";
import Calendar from "../Calendar/Calendar";
import AgentChat from "../AgentChat/AgentChat";
import OrdoLogo from "../OrdoLogo/OrdoLogo";
import { useEvents } from "../../hooks/useEvents";
import { useAgent } from "../../hooks/useAgent";
import config from "../../config";
import toast from "react-hot-toast";
import "./Layout.css";

const NAV_ITEMS = [
  { key: "overview", icon: Grid2x2, active: false },
  { key: "calendar", icon: CalendarDays, active: true },
  { key: "insights", icon: PieChart, active: false },
  { key: "messages", icon: Mail, active: false },
  { key: "work", icon: Briefcase, active: false },
];

export default function Layout() {
  const [activeCalendars, setActiveCalendars] = useState<any[]>([]);
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
    <div className="layout">
      <div className="layout-shell">
        <aside className="layout-sidebar">
          <div className="layout-brand-mark" aria-label="Ordo">
            <OrdoLogo size={36} />
          </div>

          <div className="layout-sidebar-nav">
            {NAV_ITEMS.map(({ key, icon: Icon, active }) => (
              <button
                key={key}
                type="button"
                className={`layout-sidebar-btn${active ? " active" : ""}`}
                aria-label={key}
              >
                <Icon size={18} />
              </button>
            ))}
          </div>

          <div className="layout-sidebar-footer">
            <button type="button" className="layout-sidebar-btn" aria-label="settings">
              <Settings size={18} />
            </button>
            <button type="button" className="layout-sidebar-btn" aria-label="logout">
              <LogOut size={18} />
            </button>
            <div className="layout-avatar" aria-hidden="true">
              NS
            </div>
          </div>
        </aside>

        <div className="layout-main-card">
          {/* <div className="layout-main-header">
            <div>
              <h1 className="layout-title">Morning, Nate!</h1>
              <p className="layout-subtitle">Here's what's on your agenda today.</p>
            </div>

            <div className="layout-header-actions">
              <div className="layout-search-pill">
                <span className="layout-search-icon">⌕</span>
                <span>Search for some activities</span>
              </div>
              <button type="button" className="layout-spark-btn" aria-label="spark actions">
                ✦
              </button>
            </div>
          </div> */}

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
          </div>
        </div>
      </div>

      <AgentChat
        messages={messages}
        loading={agentLoading}
        error={error}
        onSend={sendMessage}
      />
    </div>
  );
}

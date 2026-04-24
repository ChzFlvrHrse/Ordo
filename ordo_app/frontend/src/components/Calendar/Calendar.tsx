import React, { useEffect, useMemo, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid/index.js";
import timeGridPlugin from "@fullcalendar/timegrid/index.js";
import interactionPlugin from "@fullcalendar/interaction/index.js";
import { DatesSetArg, EventClickArg, EventContentArg, MoreLinkArg } from "@fullcalendar/core/index.js";
import { ChevronDown, ChevronLeft, ChevronRight, Link2, Tag } from "lucide-react";
import toast from "react-hot-toast";
import { OrdoEvent } from "../../hooks/useEvents";
import { ThirdPartyLogo } from "../../logos";
import config from "../../config";
import "./Calendar.css";

import CalendarAuthModal from "../../modal/CalendarAuthModal/CalendarAuthModal";
import CalendarLabelsModal from "../../modal/CalendarLabelsModal/CalendarLabelsModal";
import EventDetailsModal from "../../modal/EventDetailsModal/EventDetailsModal";
import ExpandedDayOverlay, {
  ExpandedDayEvent,
  ExpandedDayState,
} from "../ExpandedDayOverlay/ExpandedDayOverlay";

interface CalendarProps {
  events: OrdoEvent[];
  loading: boolean;
  activeCalendars: any[];
  date: Date;
  setDate: (date: Date) => void;
  setVisibleRange: (range: { start: Date; end: Date }) => void;
  ensureMonthsLoaded: (start: Date | null, end: Date | null) => Promise<void>;
  refetch: () => Promise<void> | void;
}

function renderEventContent(arg: EventContentArg) {
  const color = arg.event.extendedProps.color || "#4ca7ff";

  return (
    <div className="cal-event-inner">
      <div className="cal-event-bar" style={{ background: color }} />
      <div className="cal-event-content">
        <div className="cal-event-title">{arg.event.title}</div>
        {arg.timeText ? <div className="cal-event-time">{arg.timeText}</div> : null}
      </div>
    </div>
  );
}

function LabelLegend({
  integrations,
  activeLabelFilters,
  toggleLabelFilter,
}: {
  integrations: any[];
  activeLabelFilters: string[];
  toggleLabelFilter: (label: string) => void;
}) {
  const legend = React.useMemo(() => {
    const map = new Map();
    integrations.forEach((integration) => {
      const label = integration.label?.trim();
      const color = integration.color;
      if (!label || !color) return;
      if (!map.has(label)) map.set(label, { label, color });
    });
    return Array.from(map.values());
  }, [integrations]);

  if (legend.length === 0) return null;

  return (
    <div className="label-legend-wrap">
      <div className="label-legend-header">Labels</div>
      <div className="label-legend">
        {legend.map((item: any) => (
          <button
            type="button"
            key={item.label}
            onClick={() => toggleLabelFilter(item.label)}
            className={`label-legend-item${activeLabelFilters.includes(item.label) ? " active" : ""}`}
          >
            <span className="label-legend-item-color" style={{ background: item.color }} />
            <span className="label-legend-item-text">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

const VIEWS = ["Week", "Month", "Day"];

function viewLabelFromType(type: string) {
  if (type === "timeGridWeek") return "Week";
  if (type === "timeGridDay") return "Day";
  return "Month";
}

export default function Calendar({
  events,
  loading,
  activeCalendars,
  date,
  setDate,
  setVisibleRange,
  ensureMonthsLoaded,
  refetch,
}: CalendarProps) {
  const calendarRef = useRef<FullCalendar>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const connectionsMenuRef = useRef<HTMLDivElement | null>(null);

  const [activeView, setActiveView] = useState("Month");
  const [showAuthModal, setShowAuthModal] = useState<"google" | "microsoft" | "labels" | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [showConnectionsMenu, setShowConnectionsMenu] = useState(false);
  const [providerConnections, setProviderConnections] = useState<Record<string, any[]>>({});
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [labelsLoading, setLabelsLoading] = useState(false);
  const [activeLabelFilters, setActiveLabelFilters] = useState<string[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null);
  const [expandedDay, setExpandedDay] = useState<ExpandedDayState>(null);

  useEffect(() => {
    const connections = activeCalendars.reduce((acc, calendar) => {
      const key = String(calendar?.provider || "").toLowerCase().trim();
      if (!key) return acc;
      acc[key] = [...(acc[key] || []), calendar];
      return acc;
    }, {} as Record<string, any[]>);
    setProviderConnections(connections);
  }, [activeCalendars]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setActiveProvider(null);
      }
      if (connectionsMenuRef.current && !connectionsMenuRef.current.contains(e.target as Node)) {
        setShowConnectionsMenu(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!expandedDay) return;
    const close = () => setExpandedDay(null);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("resize", close);
    };
  }, [expandedDay]);

  const toggleLabelFilter = (label: string) => {
    setActiveLabelFilters((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    );
  };

  const googleConnected = (providerConnections.google || []).length > 0;
  const outlookConnected = (providerConnections.microsoft || []).length > 0;

  const filteredEvents = useMemo(() => {
    if (activeLabelFilters.length === 0) return events;
    return events.filter((e) => e.label && activeLabelFilters.includes(e.label));
  }, [events, activeLabelFilters]);

  const calendarEvents = useMemo(
    () =>
      filteredEvents.map((e) => ({
        id: e.id,
        title: e.title,
        start: e.start,
        end: e.end,
        extendedProps: {
          provider: e.provider,
          email: e.email,
          color: e.color,
          label: e.label,
          location: e.location,
          description: e.description,
          attendees: e.attendees,
          meetLink: e.meetLink,
          htmlLink: e.htmlLink,
        },
      })),
    [filteredEvents]
  );

  const handleViewChange = (view: string) => {
    const api = calendarRef.current?.getApi();
    if (!api) return;

    if (view === "Week") api.changeView("timeGridWeek");
    if (view === "Month") api.changeView("dayGridMonth");
    if (view === "Day") api.changeView("timeGridDay");
  };

  const handlePrev = () => calendarRef.current?.getApi().prev();
  const handleNext = () => calendarRef.current?.getApi().next();
  const handleToday = () => calendarRef.current?.getApi().today();

  const displayedMonth = () => {
    const api = calendarRef.current?.getApi();
    if (!api) {
      return date.toLocaleDateString("en-US", {
        month: "long",
        year: "numeric",
      });
    }

    return new Date(api.view.currentStart).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });
  };

  const handleEventClick = (arg: EventClickArg) => {
    setSelectedEvent({
      id: arg.event.id,
      title: arg.event.title,
      start: arg.event.start,
      end: arg.event.end,
      allDay: arg.event.allDay,
      extendedProps: arg.event.extendedProps,
    });
  };

  const PROVIDER_ENDPOINTS: Record<"google" | "microsoft", string> = {
    google: "/google_calendar/connect",
    microsoft: "/microsoft_calendar/connect",
  };

  const PROVIDER_DISPLAY: Record<"google" | "microsoft", string> = {
    google: "Google",
    microsoft: "Outlook",
  };

  const connectProvider = async (provider: "google" | "microsoft") => {
    setAuthLoading(true);
    try {
      const result = await fetch(`${config.apiBaseUrl}${PROVIDER_ENDPOINTS[provider]}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": config.apiKey,
        },
        body: JSON.stringify({ user_id: config.userId }),
      });
      const data = await result.json();
      if (data.success && data?.auth_url) {
        toast.loading(`Redirecting to ${PROVIDER_DISPLAY[provider]}...`);
        window.location.href = data.auth_url;
      } else {
        toast.error(data.error || `Failed to start ${PROVIDER_DISPLAY[provider]} auth`);
        setAuthLoading(false);
      }
    } catch (error) {
      toast.error(`Could not connect to ${PROVIDER_DISPLAY[provider]} Calendar`);
      setAuthLoading(false);
    }
  };

  const saveLabels = async (items: any[]) => {
    setLabelsLoading(true);
    try {
      const res = await fetch(`${config.apiBaseUrl}/integrations/labels`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": config.apiKey,
        },
        body: JSON.stringify({
          user_id: config.userId,
          labels: items.map((item) => ({
            id: item.id,
            provider: item.provider,
            email: item.email,
            label: item.label?.trim(),
            color: item.color,
          })),
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Save failed (${res.status})`);
      }

      toast.success("Labels saved");
      setShowAuthModal(null);
      await refetch();
    } catch (error: any) {
      toast.error(error?.message || "Could not save labels");
    } finally {
      setLabelsLoading(false);
    }
  };

  const openModalProvider = (provider: string, type: "oauth" | "connections") => {
    if (type === "connections") {
      setActiveProvider(provider);
      return;
    }

    if (provider === "google" || provider === "microsoft") {
      setShowAuthModal(provider);
      setActiveProvider(null);
    }

    setShowConnectionsMenu(false);
  };

  const connectionPills = {
    ordo: "Ordo",
    google: "Google",
    microsoft: "Outlook",
  };

  const getInitials = (email: string) => email?.charAt(0)?.toUpperCase() || "?";

  const handleDatesSet = async (arg: DatesSetArg) => {
    const currentDate = arg.view.currentStart;
    setDate(currentDate);
    setActiveView(viewLabelFromType(arg.view.type));

    let visibleStart = arg.start;
    let visibleEndExclusive = arg.end;

    if (arg.view.type === "dayGridMonth") {
      const viewStart = arg.view.currentStart;
      const viewEnd = new Date(arg.view.currentEnd);
      viewEnd.setMilliseconds(viewEnd.getMilliseconds() - 1);
      visibleStart = viewStart;
      visibleEndExclusive = new Date(viewEnd.getFullYear(), viewEnd.getMonth() + 1, 1);
    }

    const inclusiveVisibleEnd = new Date(visibleEndExclusive.getTime() - 1);
    setVisibleRange({ start: visibleStart, end: inclusiveVisibleEnd });
    await ensureMonthsLoaded(visibleStart, inclusiveVisibleEnd);
  };

  return (
    <>
      {(showAuthModal === "google" || showAuthModal === "microsoft") && (
        <CalendarAuthModal
          provider={showAuthModal}
          loading={authLoading}
          connected={showAuthModal === "google" ? googleConnected : outlookConnected}
          onClose={() => {
            setShowAuthModal(null);
            setAuthLoading(false);
          }}
          onConnect={() => connectProvider(showAuthModal)}
        />
      )}

      {showAuthModal === "labels" && (
        <CalendarLabelsModal
          loading={labelsLoading}
          integrations={activeCalendars}
          onClose={() => setShowAuthModal(null)}
          onSave={saveLabels}
        />
      )}

      {selectedEvent && (
        <EventDetailsModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}

      <div className="calendar-shell">
        <div className="calendar-board">
          <div className="calendar-top-row">
            <div className="calendar-period-controls">
              <button type="button" className="calendar-period-btn">
                <span>{new Intl.DateTimeFormat("en-US", { month: "long" }).format(date)}</span>
                <ChevronDown size={15} />
              </button>
              <button type="button" className="calendar-period-btn calendar-period-btn--year">
                <span>{new Intl.DateTimeFormat("en-US", { year: "numeric" }).format(date)}</span>
                <ChevronDown size={15} />
              </button>
            </div>

            <div className="calendar-board-actions">
              <button
                type="button"
                className="calendar-arrow-btn"
                onClick={handlePrev}
                aria-label="Previous"
              >
                <ChevronLeft size={18} strokeWidth={2.25} />
              </button>
              <button
                type="button"
                className="calendar-arrow-btn"
                onClick={handleNext}
                aria-label="Next"
              >
                <ChevronRight size={18} strokeWidth={2.25} />
              </button>
            </div>
          </div>

          <div className="calendar-utility-row">
            <div className="calendar-legend-wrap">
              <div className="connections-legend-wrap">
                <div className="label-legend-header">Connections</div>
                <div className="connections-legend-pills">
                  {Object.keys(connectionPills).map((provider: string) => {
                    const connections =
                      provider === "ordo"
                        ? [{ id: "ordo-system", email: "system@ordo" }]
                        : providerConnections[provider] || [];
                    const connected = connections.length > 0;
                    const label = connectionPills[provider as keyof typeof connectionPills];

                    return (
                      <div key={provider} className="source-pill-wrapper">
                        <button
                          type="button"
                          className={`source-pill ${label.toLowerCase()} ${connected ? "connected" : "inactive"}`}
                          onClick={() =>
                            connected && setActiveProvider(activeProvider === provider ? null : provider)
                          }
                          aria-expanded={activeProvider === provider}
                          title={
                            connected
                              ? `View ${label} accounts`
                              : `No ${label} accounts connected`
                          }
                        >
                          <span className={`source-dot ${label.toLowerCase()}`} />
                          {connected && connections.length > 0 && provider !== "ordo" ? (
                            <span className="source-count">{connections.length}</span>
                          ) : null}
                          {label}
                        </button>

                        {activeProvider === provider ? (
                          <div ref={popoverRef} className="provider-popover">
                            <div className="provider-popover-header">
                              {provider === "microsoft" ? (
                                <span className="provider-popover-logo">
                                  <ThirdPartyLogo name="outlook" className="" />
                                </span>
                              ) : null}
                              {provider === "google" ? (
                                <span className="provider-popover-logo">
                                  <ThirdPartyLogo name="google" className="" />
                                </span>
                              ) : null}
                              {label} accounts
                            </div>
                            <div className="provider-popover-list">
                              {provider === "ordo" ? (
                                <div className="provider-account-row">
                                  <div className="provider-account-left">
                                    <div className="provider-avatar">O</div>
                                    <div className="provider-account-email">Ordo system</div>
                                  </div>
                                  <div className="provider-account-status active">Active</div>
                                </div>
                              ) : (providerConnections[provider] || []).length === 0 ? (
                                <div className="provider-empty">No accounts connected</div>
                              ) : (
                                (providerConnections[provider] || []).map((acct: any) => {
                                  const isExpired = acct.token_expiry
                                    ? new Date(acct.token_expiry) < new Date()
                                    : false;

                                  return (
                                    <div key={acct.id} className="provider-account-row">
                                      <div className="provider-account-left">
                                        <div className="provider-avatar">{getInitials(acct.email)}</div>
                                        <div className="provider-account-email">{acct.email}</div>
                                      </div>
                                      <div className={`provider-account-status ${isExpired ? "expired" : "active"}`}>
                                        {isExpired ? "Expired" : "Active"}
                                      </div>
                                    </div>
                                  );
                                })
                              )}
                            </div>

                            {provider !== "ordo" ? (
                              <div className="provider-popover-footer">
                                <button
                                  type="button"
                                  className="provider-connect-btn"
                                  onClick={() => openModalProvider(provider, "oauth")}
                                >
                                  Connect another
                                </button>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              <LabelLegend
                integrations={activeCalendars}
                activeLabelFilters={activeLabelFilters}
                toggleLabelFilter={toggleLabelFilter}
              />
            </div>

            <div className="calendar-actions">
              <div className="connections-menu-wrap" ref={connectionsMenuRef}>
                <button
                  type="button"
                  className="oauth-action-btn labels-menu-btn"
                  onClick={() => {
                    setShowAuthModal("labels");
                    setShowConnectionsMenu(false);
                    setActiveProvider(null);
                  }}
                >
                  <Tag size={14} />
                  Labels
                </button>

                <button
                  type="button"
                  className="oauth-action-btn"
                  onClick={() => setShowConnectionsMenu((prev) => !prev)}
                >
                  <Link2 size={14} />
                  Connections
                  <ChevronDown size={14} />
                </button>

                {showConnectionsMenu ? (
                  <div className="connections-menu">
                    <button
                      type="button"
                      className="connections-menu-item"
                      onClick={() => openModalProvider("google", "oauth")}
                    >
                      <ThirdPartyLogo name="google" className="connections-menu-logo" />
                      Connect Google
                    </button>
                    <button
                      type="button"
                      className="connections-menu-item"
                      onClick={() => openModalProvider("microsoft", "oauth")}
                    >
                      <ThirdPartyLogo name="outlook" className="connections-menu-logo" />
                      Connect Outlook
                    </button>
                    {googleConnected && outlookConnected ? (
                      <div className="connections-menu-empty">All calendar providers connected</div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="calendar-view-toggle">
                {VIEWS.map((v) => (
                  <button
                    key={v}
                    className={`calendar-view-btn${activeView === v ? " active" : ""}`}
                    onClick={() => handleViewChange(v)}
                  >
                    {v}
                  </button>
                ))}
              </div>

              <button type="button" className="calendar-today-btn" onClick={handleToday}>
                Today
              </button>

              {loading ? <span className="calendar-loading">Syncing...</span> : null}
            </div>
          </div>

          <div className="displayed-month">{displayedMonth()}</div>

          <div className="calendar-grid-wrap">
            <FullCalendar
              ref={calendarRef}
              plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
              initialView="dayGridMonth"
              headerToolbar={false}
              events={calendarEvents}
              eventContent={renderEventContent}
              eventClick={handleEventClick}
              height="100%"
              expandRows
              nowIndicator
              slotMinTime="06:00:00"
              slotMaxTime="22:00:00"
              allDaySlot={true}
              dayMaxEvents={3}
              moreLinkClick={((arg: MoreLinkArg) => {
                const target = (arg.jsEvent?.currentTarget || arg.jsEvent?.target) as HTMLElement | null;
                const cell = (target?.closest(".fc-daygrid-day") as HTMLElement | null) ?? target;
                const cellRect = cell?.getBoundingClientRect();
                const fallback = target?.getBoundingClientRect();
                const source = cellRect ?? fallback;
                const rect = source
                  ? {
                    top: source.top,
                    left: source.left,
                    width: source.width,
                    height: source.height,
                  }
                  : {
                    top: window.innerHeight / 2 - 60,
                    left: window.innerWidth / 2 - 100,
                    width: 200,
                    height: 120,
                  };
                const allEvents: ExpandedDayEvent[] = [
                  ...arg.allSegs.map((s) => ({
                    id: s.event.id,
                    title: s.event.title,
                    start: s.event.start ?? null,
                    end: s.event.end ?? null,
                    allDay: s.event.allDay,
                    extendedProps: s.event.extendedProps,
                  })),
                ];
                setExpandedDay({ date: arg.date, events: allEvents, rect });
                arg.jsEvent?.preventDefault();
                return false;
              }) as any}
              datesSet={handleDatesSet}
            />
          </div>
        </div>
      </div>

      <ExpandedDayOverlay
        expandedDay={expandedDay}
        onClose={() => setExpandedDay(null)}
        onSelectEvent={(ev) => {
          setSelectedEvent({
            id: ev.id,
            title: ev.title,
            start: ev.start ?? null,
            end: ev.end ?? null,
            allDay: ev.allDay,
            extendedProps: ev.extendedProps,
          });
          setExpandedDay(null);
        }}
      />
    </>
  );
}

import React, { useEffect, useMemo, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import { DatesSetArg, EventClickArg, EventContentArg } from "@fullcalendar/core";
import { ChevronDown, Link2, Tag } from "lucide-react";
import toast from "react-hot-toast";
import { OrdoEvent } from "../../hooks/useEvents";
import config from "../../config";
import "./Calendar.css";

// Modals
import GoogleCalendarModal from "../../modal/GoogleCalendarModal/GoogleCalendarModal";
import CalendarLabelsModal from "../../modal/CalendarLabelsModal/CalendarLabelsModal";
import EventDetailsModal from "../../modal/EventDetailsModal/EventDetailsModal";

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
  const color = arg.event.extendedProps.color || "#22d3ee";
  return (
    <div className="cal-event-inner">
      <div className="cal-event-bar" style={{ background: color }} />
      <div className="cal-event-content">
        <div className="cal-event-title">{arg.event.title}</div>
        {arg.timeText && <div className="cal-event-time">{arg.timeText}</div>}
      </div>
    </div>
  );
}

function ordoLogo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <defs>
        <linearGradient id="ordoGrad" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7c3aed" />
          <stop offset="1" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
      <rect x="2" y="5" width="24" height="21" rx="4" stroke="url(#ordoGrad)" strokeWidth="1.6" />
      <rect x="8" y="2" width="2.2" height="6" rx="1.1" fill="url(#ordoGrad)" />
      <rect x="18" y="2" width="2.2" height="6" rx="1.1" fill="url(#ordoGrad)" />
      <rect x="6" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" fillOpacity="0.3" />
      <rect x="12" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" />
      <rect x="18" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" fillOpacity="0.3" />
      <rect x="6" y="18.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" fillOpacity="0.3" />
    </svg>
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
      if (!map.has(label)) {
        map.set(label, { label, color });
      }
    });
    return Array.from(map.values());
  }, [integrations]);

  if (legend.length === 0) return null;

  return (
    <>
      <div className="legend-divider"></div>
      <div className="label-legend-wrap">
        <div className="label-legend-header">Labels</div>
        <div className="label-legend">
          {legend.map((item: any) => (
            <div
              key={item.label}
              onClick={() => toggleLabelFilter(item.label)}
              className={`label-legend-item${activeLabelFilters.includes(item.label) ? " active" : ""}`}
            >
              <span className="label-legend-item-color" style={{ background: item.color }} />
              <span className="label-legend-item-text">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </>
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
  const [showAuthModal, setShowAuthModal] = useState<string | null>(null);
  const [googleCalendarLoading, setGoogleCalendarLoading] = useState(false);
  const [showConnectionsMenu, setShowConnectionsMenu] = useState(false);
  const [providerConnections, setProviderConnections] = useState<Record<string, any[]>>({});
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [labelsLoading, setLabelsLoading] = useState(false);
  const [activeLabelFilters, setActiveLabelFilters] = useState<string[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null);

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

  const toggleLabelFilter = (label: string) => {
    setActiveLabelFilters((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    );
  };

  const googleConnected = (providerConnections.google || []).length > 0;
  const outlookConnected = (providerConnections.outlook || []).length > 0;

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

  const todaysDate = new Date().toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    // year: "numeric",
  });
  const displayedMonth = () => {
    const api = calendarRef.current?.getApi();
    if (!api) return null;
    return new Date(api.view.currentStart).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });
  }

  const handleEventClick = (arg: EventClickArg) => {
    console.log("Event clicked:", arg.event.title);
    setSelectedEvent({
      id: arg.event.id,
      title: arg.event.title,
      start: arg.event.start,
      end: arg.event.end,
      allDay: arg.event.allDay,
      extendedProps: arg.event.extendedProps,
    });
  };

  const connectGoogleCalendar = async () => {
    setGoogleCalendarLoading(true);
    try {
      const result = await fetch(`${config.apiBaseUrl}/google_calendar/connect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": config.apiKey,
        },
        body: JSON.stringify({ user_id: config.userId }),
      });
      const data = await result.json();
      if (data.success && data?.auth_url) {
        toast.loading("Redirecting to Google...");
        window.location.href = data.auth_url;
      } else {
        toast.error(data.error || "Failed to start Google auth");
        setGoogleCalendarLoading(false);
      }
    } catch (error) {
      toast.error("Could not connect to Google Calendar");
      setGoogleCalendarLoading(false);
    }
  };

  const saveLabels = async (items: any[]) => {
    setLabelsLoading(true);
    try {
      await Promise.all(
        items.map((item) =>
          fetch(`${config.apiBaseUrl}/integrations/labels`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "X-API-Key": config.apiKey,
            },
            body: JSON.stringify({
              user_id: config.userId,
              provider: item.provider,
              email: item.email,
              label: item.label?.trim(),
              color: item.color,
            }),
          })
        )
      );
      toast.success("Labels saved");
      setShowAuthModal(null);
      await refetch();
    } catch (error) {
      toast.error("Could not save labels");
    } finally {
      setLabelsLoading(false);
    }
  };

  const openModalProvider = (provider: string, type: "oauth" | "connections") => {
    if (type === "connections") {
      setActiveProvider(provider);
      return;
    }

    switch (provider) {
      case "google":
        setShowAuthModal("google");
        setActiveProvider(null);
        break;
      case "outlook":
        setActiveProvider(null);
        setShowConnectionsMenu(false);
        break;
      default:
        break;
    }

    setShowConnectionsMenu(false);
  };

  const connectionPills = ["ordo", "google", "outlook"];
  const getProviderLabel = (provider: string) =>
    provider.charAt(0).toUpperCase() + provider.slice(1);
  const getInitials = (email: string) => email?.charAt(0)?.toUpperCase() || "?";

  const handleDatesSet = async (info: DatesSetArg) => {
    setActiveView(viewLabelFromType(info.view.type));
    setDate(new Date(info.view.currentStart));
    setVisibleRange({
      start: new Date(info.start),
      end: new Date(info.end),
    });

    await ensureMonthsLoaded(new Date(info.start), new Date(info.end));
  };

  return (
    <>
      {showAuthModal === "google" && (
        <GoogleCalendarModal
          loading={googleCalendarLoading}
          onClose={() => setShowAuthModal(null)}
          onConnect={connectGoogleCalendar}
          connected={googleConnected}
        />
      )}

      {showAuthModal === "labels" && (
        <CalendarLabelsModal
          integrations={activeCalendars}
          loading={labelsLoading}
          onClose={() => setShowAuthModal(null)}
          onSave={async (items: any[]) => {
            await saveLabels(items);
          }}
        />
      )}

      {selectedEvent && (
        <EventDetailsModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}

      <div className="calendar-wrap">
        <div className="calendar-topbar">
          <div className="calendar-logo">
            <div className="calendar-logo-icon">
              {ordoLogo()}
              <div className="calendar-logo-sparkle">
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#a5f3fc"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2L9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z" />
                </svg>
              </div>
            </div>
            <div>
              <div className="calendar-logo-text">Ordo</div>
              <div className="calendar-logo-sub">AI scheduling layer</div>
            </div>
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
        </div>

        <div className="calendar-toolbar">
          <div className="calendar-title-group">
            <span className="calendar-badge">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M15 4V2M15 4V6M15 4H10.5M3 10V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V10H3ZM3 10V6C3 4.9 3.9 4 5 4H7" />
                <path d="M7 2V6" />
                <path d="M21 10V6C21 4.9 20.1 4 19 4H18.5" />
              </svg>
              AI calendar
            </span>
            <div className="calendar-month">{todaysDate}</div>
          </div>


          <div className="calendar-nav">
            <button className="calendar-nav-btn" onClick={handlePrev}>‹</button>
            <button className="calendar-today-btn" onClick={handleToday}>Today</button>
            <button className="calendar-nav-btn" onClick={handleNext}>›</button>
          </div>
        </div>

        <div className="calendar-filters">
          <div className="calendar-legend-wrap">
            <div className="connections-legend-wrap">
              <div className="label-legend-header">Connections</div>
              <div className="connections-legend-pills">
                {connectionPills.map((provider) => {
                  const connections =
                    provider === "ordo"
                      ? [{ id: "ordo-system", email: "system@ordo" }]
                      : providerConnections[provider] || [];
                  const connected = connections.length > 0;

                  return (
                    <div key={provider} className="source-pill-wrapper">
                      <button
                        type="button"
                        className={`source-pill ${provider} ${connected ? "connected" : "inactive"}`}
                        onClick={() =>
                          connected && setActiveProvider(activeProvider === provider ? null : provider)
                        }
                      >
                        <span className={`source-dot ${provider}`} />
                        {connected && connections.length > 0 && provider !== "ordo" && (
                          <span className="source-count">{connections.length}</span>
                        )}
                        {getProviderLabel(provider)}
                      </button>

                      {activeProvider === provider && (
                        <div ref={popoverRef} className="provider-popover">
                          <div className="provider-popover-header">
                            {getProviderLabel(provider)} accounts
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
                                    <div
                                      className={`provider-account-status ${isExpired ? "expired" : "active"}`}
                                    >
                                      {isExpired ? "Expired" : "Active"}
                                    </div>
                                  </div>
                                );
                              })
                            )}
                          </div>

                          {provider !== "ordo" && (
                            <div className="provider-popover-footer">
                              <button
                                className="provider-connect-btn"
                                onClick={() => openModalProvider(provider, "oauth")}
                              >
                                Connect another
                              </button>
                            </div>
                          )}
                        </div>
                      )}
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

              {showConnectionsMenu && (
                <div className="connections-menu">
                  <button
                    type="button"
                    className="connections-menu-item"
                    onClick={() => openModalProvider("google", "oauth")}
                  >
                    Connect Google
                  </button>
                  <button
                    type="button"
                    className="connections-menu-item"
                    onClick={() => openModalProvider("outlook", "oauth")}
                  >
                    Connect Outlook
                  </button>
                  {googleConnected && outlookConnected && (
                    <div className="connections-menu-empty">
                      All calendar providers connected
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="filter-pill">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
              Filters
            </div>

            {loading && <span className="calendar-loading">Syncing...</span>}
          </div>
        </div>

        <div className="displayed-month">
          {displayedMonth()}
        </div>

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
            nowIndicator
            slotMinTime="06:00:00"
            slotMaxTime="22:00:00"
            allDaySlot={true}
            dayMaxEvents={3}
            datesSet={handleDatesSet}
          />
        </div>
      </div>
    </>
  );
}

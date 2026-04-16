import React, { useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import { EventClickArg, EventContentArg } from "@fullcalendar/core";
import { OrdoEvent } from "../../hooks/useEvents";
import "./Calendar.css";

interface CalendarProps {
  events: OrdoEvent[];
  loading: boolean;
}

const PROVIDER_COLORS: Record<string, string> = {
  google: "google",
  outlook: "outlook",
  ordo: "ordo",
  teli: "teli",
};

function renderEventContent(arg: EventContentArg) {
  const provider = (arg.event.extendedProps.provider as string) || "ordo";
  const barClass = PROVIDER_COLORS[provider] || "ordo";
  return (
    <div className="cal-event-inner">
      <div className={`cal-event-bar ${barClass}`} />
      <div className="cal-event-content">
        <div>
          <div className="cal-event-title">{arg.event.title}</div>
          {arg.timeText && <div className="cal-event-time">{arg.timeText}</div>}
        </div>
        <div className="cal-event-source">{provider}</div>
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
  )
}

const VIEWS = ["Week", "Month", "Day"];

export default function Calendar({ events, loading }: CalendarProps) {
  const calendarRef = useRef<FullCalendar>(null);
  const [activeView, setActiveView] = useState("Week");

  const calendarEvents = events.map((e) => ({
    id: e.id,
    title: e.title,
    start: e.start,
    end: e.end,
    extendedProps: {
      provider: e.provider,
      location: e.location,
      description: e.description,
      attendees: e.attendees,
    },
  }));

  const handleViewChange = (view: string) => {
    setActiveView(view);
    const api = calendarRef.current?.getApi();
    if (view === "Week") api?.changeView("timeGridWeek");
    if (view === "Month") api?.changeView("dayGridMonth");
    if (view === "Day") api?.changeView("timeGridDay");
  };

  const handlePrev = () => calendarRef.current?.getApi().prev();
  const handleNext = () => calendarRef.current?.getApi().next();
  const handleToday = () => calendarRef.current?.getApi().today();

  const handleEventClick = (arg: EventClickArg) => {
    console.log("Event clicked:", arg.event.title);
  };

  return (
    <div className="calendar-wrap">
      <div className="calendar-topbar">
        <div className="calendar-logo">
          <div className="calendar-logo-icon">
            {ordoLogo()}
            <div className="calendar-logo-sparkle">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#a5f3fc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 4V2M15 4V6M15 4H10.5M3 10V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V10H3ZM3 10V6C3 4.9 3.9 4 5 4H7" />
              <path d="M7 2V6" />
              <path d="M21 10V6C21 4.9 20.1 4 19 4H18.5" />
            </svg>
            AI calendar
          </span>
          <div className="calendar-month">April 2026</div>
        </div>

        <div className="calendar-nav">
          <button className="calendar-nav-btn" onClick={handlePrev}>‹</button>
          <button className="calendar-today-btn" onClick={handleToday}>Today</button>
          <button className="calendar-nav-btn" onClick={handleNext}>›</button>
        </div>
      </div>

      <div className="calendar-filters">
        {[
          { label: "Google", key: "google" },
          { label: "Outlook", key: "outlook" },
          { label: "Ordo", key: "ordo" },
        ].map(({ label, key }) => (
          <div key={key} className={`source-pill ${key}`}>
            <span className={`source-dot ${key}`} />
            {label}
          </div>
        ))}
        <div className="filter-pill">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          Filters
        </div>
        {loading && <span className="calendar-loading">Syncing...</span>}
      </div>

      <div className="calendar-grid-wrap">
        <FullCalendar
          ref={calendarRef}
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="timeGridWeek"
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
        />
      </div>
    </div>
  );
}

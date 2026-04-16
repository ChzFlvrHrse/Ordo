import React, { useRef } from "react";
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
  google: "#4f46e5",
  outlook: "#0ea5e9",
  ordo: "#7c3aed",
};

function renderEventContent(arg: EventContentArg) {
  const provider = arg.event.extendedProps.provider as string;
  const color = PROVIDER_COLORS[provider] || PROVIDER_COLORS.ordo;
  return (
    <div className="cal-event-inner" style={{ borderLeftColor: color }}>
      <span className="cal-event-title">{arg.event.title}</span>
      {arg.timeText && <span className="cal-event-time">{arg.timeText}</span>}
    </div>
  );
}

export default function Calendar({ events, loading }: CalendarProps) {
  const calendarRef = useRef<FullCalendar>(null);

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

  const handleEventClick = (arg: EventClickArg) => {
    const { title, start, end, extendedProps } = arg.event;
    console.log("Event clicked:", { title, start, end, ...extendedProps });
  };

  return (
    <div className="calendar-wrap">
      {loading && <div className="calendar-loading">Syncing...</div>}
      <FullCalendar
        ref={calendarRef}
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        initialView="timeGridWeek"
        headerToolbar={{
          left: "prev,next today",
          center: "title",
          right: "dayGridMonth,timeGridWeek,timeGridDay",
        }}
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
  );
}

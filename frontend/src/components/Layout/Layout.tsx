import React, { useState, useCallback, useEffect } from "react";
import Calendar from "../Calendar/Calendar";
import AgentChat from "../AgentChat/AgentChat";
import { useEvents } from "../../hooks/useEvents";
import { useAgent } from "../../hooks/useAgent";
import config from "../../config";
import toast from "react-hot-toast";
import "./Layout.css";

export default function Layout() {
  const { events, loading: eventsLoading, refetch } = useEvents();
  const { messages, loading: agentLoading, error, sendMessage } = useAgent(refetch);
  const [activeCalendars, setActiveCalendars] = useState<any[]>([]);
  const [dragging, setDragging] = useState(false);

  const onMouseDown = useCallback(() => setDragging(true), []);
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
  }, [dragging]);
  const onMouseUp = useCallback(() => setDragging(false), []);

  const fetchActiveCalendars = async () => {
    try {
      const result = await fetch(`${config.apiBaseUrl}/integrations/calendars?user_id=${config.userId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": config.apiKey,
        }
      });

      if (!result.ok) {
        return;
      }
      const data = await result.json();
      setActiveCalendars(data.calendars ?? []);
    } catch (error) {
      toast.error("Could not load calendar connections");
      setActiveCalendars([]);
    }
  };

  useEffect(() => {
    fetchActiveCalendars();
  }, []);

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
            refetch={fetchActiveCalendars}
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

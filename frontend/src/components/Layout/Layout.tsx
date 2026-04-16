import React, { useState, useCallback, useEffect } from "react";
import Calendar from "../Calendar/Calendar";
import AgentChat from "../AgentChat/AgentChat";
import { useEvents } from "../../hooks/useEvents";
import { useAgent } from "../../hooks/useAgent";
import "./Layout.css";

export default function Layout() {
  const { events, loading: eventsLoading, refetch } = useEvents();
  const { messages, loading: agentLoading, error, sendMessage } = useAgent(refetch);
  const [dragging, setDragging] = useState(false);

  const onMouseDown = useCallback(() => setDragging(true), []);
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
  }, [dragging]);
  const onMouseUp = useCallback(() => setDragging(false), []);

  return (
    <div
      className={`layout${dragging ? " layout--dragging" : ""}`}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      <div className="layout-inner">
        <div className="layout-calendar">
          <Calendar events={events} loading={eventsLoading} />
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

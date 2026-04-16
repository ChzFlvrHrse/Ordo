import React, { useState, useCallback } from "react";
import Calendar from "../Calendar/Calendar";
import AgentChat from "../AgentsChat/AgentsChat";
import { useEvents } from "../../hooks/useEvents";
import { useAgent } from "../../hooks/useAgent";
import "./Layout.css";

export default function Layout() {
  const { events, loading: eventsLoading, refetch } = useEvents();
  const { messages, loading: agentLoading, error, sendMessage } = useAgent(refetch);
  const [dragging, setDragging] = useState(false);
  const [splitPct, setSplitPct] = useState(62);

  const onMouseDown = useCallback(() => setDragging(true), []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    const pct = (e.clientX / window.innerWidth) * 100;
    setSplitPct(Math.min(Math.max(pct, 35), 75));
  }, [dragging]);

  const onMouseUp = useCallback(() => setDragging(false), []);

  return (
    <div
      className={`layout${dragging ? " layout--dragging" : ""}`}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      <div className="layout-calendar" style={{ width: `${splitPct}%` }}>
        <Calendar events={events} loading={eventsLoading} />
      </div>

      <div className="layout-divider" onMouseDown={onMouseDown}>
        <div className="divider-handle" />
      </div>

      <div className="layout-agent" style={{ width: `${100 - splitPct}%` }}>
        <AgentChat
          messages={messages}
          loading={agentLoading}
          error={error}
          onSend={sendMessage}
        />
      </div>
    </div>
  );
}

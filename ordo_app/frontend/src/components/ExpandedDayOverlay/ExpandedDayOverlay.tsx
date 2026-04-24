import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./ExpandedDayOverlay.css";

export type ExpandedDayEvent = {
  id?: string;
  title: string;
  start?: Date | string | null;
  end?: Date | string | null;
  allDay?: boolean;
  extendedProps?: any;
};

export type ExpandedDayState = {
  date: Date;
  rect: { top: number; left: number; width: number; height: number };
  events: ExpandedDayEvent[];
} | null;

interface Props {
  expandedDay: ExpandedDayState;
  onClose: () => void;
  onSelectEvent?: (event: ExpandedDayEvent) => void;
}

const ANIM_MS = 320;
const MAX_CARD_WIDTH = 380;
const MIN_CARD_WIDTH = 320;
const MAX_CARD_HEIGHT_RATIO = 0.7;

function formatDate(date: Date) {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatTime(value: Date | string | null | undefined) {
  if (!value) return "";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d
    .toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: d.getMinutes() ? "2-digit" : undefined,
    })
    .toLowerCase()
    .replace(" ", "");
}

export default function ExpandedDayOverlay({ expandedDay, onClose, onSelectEvent }: Props) {
  const [snapshot, setSnapshot] = useState<ExpandedDayState>(null);
  const [isOpen, setIsOpen] = useState(false);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (expandedDay) {
      if (closeTimerRef.current) {
        window.clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      setSnapshot(expandedDay);
      setIsOpen(false);
      const id = window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => setIsOpen(true));
      });
      return () => window.cancelAnimationFrame(id);
    }

    if (snapshot) {
      setIsOpen(false);
      closeTimerRef.current = window.setTimeout(() => {
        setSnapshot(null);
        closeTimerRef.current = null;
      }, ANIM_MS);
    }
    return undefined;
  }, [expandedDay]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!snapshot) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [snapshot, onClose]);

  useEffect(() => {
    if (!snapshot) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [snapshot]);

  useLayoutEffect(() => {
    if (!snapshot || !isOpen || !cardRef.current) return;
    cardRef.current.focus({ preventScroll: true });
  }, [snapshot, isOpen]);

  if (!snapshot) return null;

  const { rect, date, events } = snapshot;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const margin = 24;

  const finalWidth = Math.max(
    MIN_CARD_WIDTH,
    Math.min(MAX_CARD_WIDTH, vw - margin * 2),
  );
  const naturalHeight = Math.min(vh * MAX_CARD_HEIGHT_RATIO, 640);
  const finalHeight = Math.max(320, naturalHeight);
  const finalLeft = Math.max(margin, (vw - finalWidth) / 2);
  const finalTop = Math.max(margin, (vh - finalHeight) / 2 - 12);

  const cardStyle: React.CSSProperties = isOpen
    ? {
        top: finalTop,
        left: finalLeft,
        width: finalWidth,
        height: finalHeight,
        borderRadius: 20,
      }
    : {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        borderRadius: 18,
      };

  return createPortal(
    <div
      className={`expanded-day-overlay${isOpen ? " is-open" : ""}`}
      role="presentation"
    >
      <div
        className="expanded-day-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={cardRef}
        className={`expanded-day-card${isOpen ? " is-open" : ""}`}
        style={cardStyle}
        role="dialog"
        aria-modal="true"
        aria-label={formatDate(date)}
        tabIndex={-1}
      >
        <div className="expanded-day-header">
          <div className="expanded-day-title">{formatDate(date)}</div>
          <button
            type="button"
            className="expanded-day-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="expanded-day-list">
          {events.length === 0 ? (
            <div className="expanded-day-empty">No events.</div>
          ) : (
            events.map((ev, i) => {
              const color = ev.extendedProps?.color || "#60a5fa";
              const timeText = formatTime(ev.start ?? null);
              return (
                <button
                  type="button"
                  key={ev.id ?? `${ev.title}-${i}`}
                  className="expanded-day-event"
                  onClick={() => onSelectEvent?.(ev)}
                >
                  <span
                    className="expanded-day-event-accent"
                    style={{ background: color }}
                  />
                  <span className="expanded-day-event-content">
                    <span className="expanded-day-event-title">{ev.title}</span>
                    {timeText ? (
                      <span className="expanded-day-event-time">{timeText}</span>
                    ) : null}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

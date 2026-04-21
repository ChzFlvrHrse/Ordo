import React from "react";
import { GoogleLogo, OutlookLogo } from "../../logos";
import "./EventDetailsModal.css";

interface EventDetailsModalProps {
    event: {
        id: string;
        title: string;
        start: Date | null;
        end: Date | null;
        allDay: boolean;
        extendedProps: {
            provider?: string;
            email?: string;
            color?: string;
            label?: string;
            location?: string;
            description?: string;
            attendees?: string[];
            meetLink?: string | null;
            htmlLink?: string | null;
        };
    } | null;
    onClose: () => void;
}

function formatEventDate(start: Date | null, end: Date | null, allDay: boolean) {
    if (!start) return "No date";

    if (allDay) {
        return start.toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
        });
    }

    const sameDay = !!end && start.toDateString() === end.toDateString();

    const startDate = start.toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
    });

    const startTime = start.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
    });

    const endTime = end
        ? end.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
        })
        : null;

    if (sameDay) {
        return `${startDate} · ${startTime}${endTime ? ` – ${endTime}` : ""}`;
    }

    const endDate = end
        ? end.toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
        })
        : null;

    return `${startDate} ${startTime}${end ? ` → ${endDate} ${endTime}` : ""}`;
}

function extractLinks(text?: string) {
    if (!text) return [];
    const matches = text.match(/https?:\/\/[^\s<>"')]+/g) || [];
    return Array.from(new Set(matches));
}

function safeUrl(url: string) {
    try {
        return new URL(url);
    } catch {
        return null;
    }
}

function getHostname(url: string) {
    const parsed = safeUrl(url);
    if (!parsed) return url;
    return parsed.hostname.replace(/^www\./, "");
}

function getDisplayLabel(url: string) {
    const lower = url.toLowerCase();

    if (lower.includes("meet.google.com")) return "Google Meet";
    if (lower.includes("teams.microsoft.com")) return "Microsoft Teams";
    if (lower.includes("zoom.us")) return "Zoom";
    if (lower.includes("calendar.google.com") || lower.includes("google.com/calendar")) {
        return "Google Calendar";
    }

    return getHostname(url);
}

function isPrimaryMeetingLink(url: string) {
    const lower = url.toLowerCase();
    return (
        lower.includes("meet.google.com") ||
        lower.includes("teams.microsoft.com/meet") ||
        lower.includes("teams.microsoft.com/l/meetup-join") ||
        lower.includes("zoom.us/j/")
    );
}

function isJunkLink(url: string) {
    const lower = url.toLowerCase();

    return (
        lower.includes("aka.ms/jointeamsmeeting") ||
        lower.includes("meetingoptions")
    );
}

function ProviderLogo({ provider }: { provider?: string }) {
    const normalized = (provider || "").toLowerCase();

    if (normalized === "google") {
        return (
            <div className="event-provider-logo" aria-hidden="true">
                <GoogleLogo className="event-provider-logo-svg" />
            </div>
        );
    }

    if (normalized === "microsoft") {
        return (
            <div className="event-provider-logo" aria-hidden="true">
                <OutlookLogo className="event-provider-logo-svg" />
            </div>
        );
    }

    return (
        <div className="event-provider-logo fallback" aria-hidden="true">
            {(provider || "?").slice(0, 1).toUpperCase()}
        </div>
    );
}

export default function EventDetailsModal({
    event,
    onClose,
}: EventDetailsModalProps) {
    React.useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    if (!event) return null;

    const { title, start, end, allDay, extendedProps } = event;

    const descriptionLinks = extractLinks(extendedProps.description);

    const allLinks = Array.from(
        new Set(
            [
                ...(extendedProps.meetLink ? [extendedProps.meetLink] : []),
                ...(extendedProps.htmlLink ? [extendedProps.htmlLink] : []),
                ...descriptionLinks,
            ]
                .filter(Boolean)
                .filter((link) => !isJunkLink(link)) as string[]
        )
    );

    const primaryMeetingLinks = allLinks.filter(isPrimaryMeetingLink);

    const calendarLinks = allLinks.filter((link) => {
        const lower = link.toLowerCase();
        return (
            lower.includes("calendar.google.com") ||
            lower.includes("google.com/calendar")
        );
    });

    const extraLinks = allLinks.filter(
        (link) =>
            !primaryMeetingLinks.includes(link) &&
            !calendarLinks.includes(link)
    );

    const primaryActionLink =
        primaryMeetingLinks[0] || extendedProps.meetLink || null;

    const googleCalendarLink =
        extendedProps.htmlLink || calendarLinks[0] || null;

    const extraDescription = extendedProps.description
        ? extendedProps.description
            .split("\n")
            .filter((line) => !line.match(/https?:\/\/[^\s<>"')]+/g))
            .join("\n")
            .trim()
        : "";

    return (
        <div className="event-modal-overlay" onClick={onClose}>
            <div className="event-modal" onClick={(e) => e.stopPropagation()}>
                <button className="event-modal-close" onClick={onClose} aria-label="Close">
                    ×
                </button>

                <div className="event-modal-header">
                    <div
                        className="event-modal-accent"
                        style={{ background: extendedProps.color || "#22d3ee" }}
                    />

                    <div className="event-modal-header-main">
                        <div className="event-modal-topline">
                            <div className="event-modal-title">{title}</div>

                            {extendedProps.provider && (
                                <div className="event-provider-pill">
                                    <ProviderLogo provider={extendedProps.provider} />
                                    <span>{extendedProps.provider}</span>
                                </div>
                            )}
                        </div>

                        <div className="event-modal-time">
                            {formatEventDate(start, end, allDay)}
                        </div>
                    </div>
                </div>

                <div className="event-modal-body">
                    {(primaryActionLink || googleCalendarLink || extraLinks.length > 0) && (
                        <div className="event-modal-section">
                            <div className="event-modal-section-title">Links</div>

                            <div className="event-modal-links">
                                {primaryActionLink && (
                                    <a
                                        href={primaryActionLink}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="event-link primary"
                                    >
                                        Join via {getDisplayLabel(primaryActionLink)}
                                    </a>
                                )}

                                {googleCalendarLink && (
                                    <a
                                        href={googleCalendarLink}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="event-link"
                                    >
                                        Open in Google Calendar
                                    </a>
                                )}

                                {extraLinks.slice(0, 2).map((link) => (
                                    <a
                                        key={link}
                                        href={link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="event-link"
                                        title={link}
                                    >
                                        {getDisplayLabel(link)}
                                    </a>
                                ))}
                            </div>

                            {extraLinks.length > 2 && (
                                <details className="event-more-links">
                                    <summary>Show more links</summary>
                                    <div className="event-more-links-list">
                                        {extraLinks.slice(2).map((link) => (
                                            <a
                                                key={link}
                                                href={link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="event-more-link-item"
                                                title={link}
                                            >
                                                {link}
                                            </a>
                                        ))}
                                    </div>
                                </details>
                            )}
                        </div>
                    )}

                    <div className="event-modal-grid">
                        {extendedProps.label && (
                            <div className="event-modal-card">
                                <div className="event-modal-card-label">Label</div>
                                <div className="event-modal-card-value">{extendedProps.label}</div>
                            </div>
                        )}

                        {extendedProps.location && (
                            <div className="event-modal-card">
                                <div className="event-modal-card-label">Location</div>
                                <div className="event-modal-card-value">{extendedProps.location}</div>
                            </div>
                        )}

                        {extendedProps.email && (
                            <div className="event-modal-card">
                                <div className="event-modal-card-label">Calendar</div>
                                <div className="event-modal-card-value">{extendedProps.email}</div>
                            </div>
                        )}
                    </div>

                    {extendedProps.attendees?.length ? (
                        <div className="event-modal-section">
                            <div className="event-modal-section-title">Attendees</div>
                            <div className="event-modal-attendees">
                                {extendedProps.attendees.map((attendee: string) => (
                                    <div key={attendee} className="event-modal-attendee">
                                        {attendee}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : null}

                    {(extraDescription || extendedProps.description) && (
                        <div className="event-modal-section">
                            <div className="event-modal-section-title">Description</div>
                            <div className="event-modal-description">
                                {extraDescription || extendedProps.description}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

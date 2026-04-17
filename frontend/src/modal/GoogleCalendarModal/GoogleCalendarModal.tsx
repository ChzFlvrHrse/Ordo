import React from "react";
import { ArrowRight, CheckCircle2, ShieldCheck, X, Sparkles } from "lucide-react";
import "./GoogleCalendarModal.css";

function GoogleLogo() {
    return (
        <svg viewBox="0 0 48 48" width="16" height="16">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
        </svg>
    );
}

function OrdoMark() {
    return (
        <svg viewBox="0 0 28 28" width="28" height="28">
            <defs>
                <linearGradient id="ordoGrad" x1="2" y1="2" x2="26" y2="26">
                    <stop stopColor="#22D3EE" />
                    <stop offset="1" stopColor="#0EA5E9" />
                </linearGradient>
            </defs>

            <rect x="2" y="5" width="24" height="21" rx="5" stroke="url(#ordoGrad)" strokeWidth="1.6" />
            <rect x="8" y="2" width="2.2" height="6" rx="1.1" fill="url(#ordoGrad)" />
            <rect x="18" y="2" width="2.2" height="6" rx="1.1" fill="url(#ordoGrad)" />
            <rect x="6" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" opacity="0.35" />
            <rect x="12" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" />
            <rect x="18" y="12.5" width="4" height="4" rx="1.1" fill="url(#ordoGrad)" opacity="0.35" />
        </svg>
    );
}

interface Props {
    loading: boolean;
    onClose: () => void;
    onConnect: () => void;
    connected?: boolean;
}

export default function GoogleCalendarModal({
    loading,
    onClose,
    onConnect,
    connected = false,
}: Props) {
    return (
        <div className="ordo-modal-overlay">
            <div className="ordo-modal-backdrop" onClick={onClose} />

            <div className="ordo-modal">
                <button className="ordo-modal-close" onClick={onClose}>
                    <X size={14} />
                </button>

                <div className="ordo-modal-header">
                    <div className="ordo-logo">
                        <OrdoMark />
                        <div className="ordo-sparkle">
                            <Sparkles size={10} />
                        </div>
                    </div>

                    <div>
                        <div className="ordo-title">Connect Google Calendar</div>
                        <div className="ordo-sub">
                            Let Ordo manage scheduling with live calendar access
                        </div>
                    </div>
                </div>

                <div className="ordo-connection-row">
                    <GoogleLogo />
                    <div className="ordo-connection-text">
                        <div>Google Calendar</div>
                        <span>Secure OAuth connection</span>
                    </div>

                    {connected ? (
                        <div className="ordo-badge success">
                            <CheckCircle2 size={12} /> Connected
                        </div>
                    ) : (
                        <span className="ordo-muted">Not connected</span>
                    )}
                </div>

                <div className="ordo-permissions">
                    <div className="ordo-permissions-title">Ordo will be able to</div>

                    <div className="ordo-permission">
                        <ShieldCheck size={14} />
                        Check availability before booking
                    </div>
                    <div className="ordo-permission">
                        <ShieldCheck size={14} />
                        Create and manage events
                    </div>
                    <div className="ordo-permission">
                        <ShieldCheck size={14} />
                        Send invites automatically
                    </div>
                </div>

                <button
                    className="ordo-cta"
                    onClick={onConnect}
                    disabled={loading}
                >
                    {loading ? (
                        <div className="spinner" />
                    ) : (
                        <>
                            <GoogleLogo />
                            Continue with Google
                            <ArrowRight size={14} />
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

import React from "react";
import { ArrowRight, CheckCircle2, ShieldCheck, X, Sparkles } from "lucide-react";
import { GoogleLogo, OutlookLogo } from "../../logos";
import "./CalendarAuthModal.css";

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
    provider: "google" | "microsoft";
    connected?: boolean;
}

const PROVIDER_LABELS: Record<Props["provider"], string> = {
    google: "Google",
    microsoft: "Outlook",
};

export default function CalendarAuthModal({
    loading,
    onClose,
    onConnect,
    provider,
    connected = false,
}: Props) {
    const providerLabel = PROVIDER_LABELS[provider];

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
                        <div className="ordo-title">Connect {providerLabel} Calendar</div>
                        <div className="ordo-sub">
                            Let Ordo manage scheduling with live calendar access
                        </div>
                    </div>
                </div>

                <div className="ordo-connection-row">
                    {provider === "google" && <GoogleLogo className="ordo-connection-logo" />}
                    {provider === "microsoft" && <OutlookLogo className="ordo-connection-logo" />}
                    <div className="ordo-connection-text">
                        <div>{providerLabel} Calendar</div>
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
                            {provider === "google" && <GoogleLogo className="ordo-cta-logo" />}
                            {provider === "microsoft" && <OutlookLogo className="ordo-cta-logo" />}
                            Continue with {providerLabel}
                            <ArrowRight size={14} />
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

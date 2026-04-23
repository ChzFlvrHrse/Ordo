import React from "react";
import { ArrowRight, CheckCircle2, ShieldCheck, X, Sparkles } from "lucide-react";
import { ThirdPartyLogo } from "../../logos";
import "./CalendarAuthModal.css";

function OrdoMark() {
    return (
        <svg viewBox="0 0 28 28" width="28" height="28" fill="none" aria-hidden="true">
            <defs>
                <linearGradient id="ordoGrad" x1="2" y1="2" x2="26" y2="26">
                    <stop stopColor="#60A5FA" />
                    <stop offset="1" stopColor="#A78BFA" />
                </linearGradient>
            </defs>

            <rect x="4" y="4" width="20" height="20" rx="6" stroke="url(#ordoGrad)" strokeWidth="1.8" />
            <rect x="9" y="9" width="4" height="4" rx="1.4" fill="url(#ordoGrad)" />
            <rect x="15" y="9" width="4" height="4" rx="1.4" fill="url(#ordoGrad)" />
            <rect x="9" y="15" width="4" height="4" rx="1.4" fill="url(#ordoGrad)" />
            <rect x="15" y="15" width="4" height="4" rx="1.4" fill="url(#ordoGrad)" />
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

            <div
                className="ordo-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="ordo-modal-title"
                aria-describedby="ordo-modal-description"
            >
                <button className="ordo-modal-close" onClick={onClose} aria-label="Close modal">
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
                        <div id="ordo-modal-title" className="ordo-title">
                            Connect {providerLabel} Calendar
                        </div>
                        <div id="ordo-modal-description" className="ordo-sub">
                            Let Ordo manage scheduling with live calendar access.
                        </div>
                    </div>
                </div>

                <div className="ordo-connection-row">
                    {provider === "google" && <ThirdPartyLogo name="google" className="ordo-connection-logo" />}
                    {provider === "microsoft" && <ThirdPartyLogo name="outlook" className="ordo-connection-logo" />}

                    <div className="ordo-connection-text">
                        <div>{providerLabel} Calendar</div>
                        <span>Secure OAuth connection</span>
                    </div>

                    {connected ? (
                        <div className="ordo-badge success">
                            <CheckCircle2 size={12} />
                            Connected
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

                <button className="ordo-cta" onClick={onConnect} disabled={loading}>
                    {loading ? (
                        <div className="spinner" />
                    ) : (
                        <>
                            {provider === "google" && <ThirdPartyLogo name="google" className="ordo-cta-logo" />}
                            {provider === "microsoft" && <ThirdPartyLogo name="outlook" className="ordo-cta-logo" />}
                            Continue with {providerLabel}
                            <ArrowRight size={14} />
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

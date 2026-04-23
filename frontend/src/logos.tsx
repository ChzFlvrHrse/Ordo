import outlookLogo from "./assets/outlook-logo.png";
import googleLogo from "./assets/google-logo.png";

export type ThirdPartyLogoName = "outlook" | "google";

const LOGOS: Record<ThirdPartyLogoName, { src: string; alt: string }> = {
    outlook: { src: outlookLogo, alt: "Outlook" },
    google: { src: googleLogo, alt: "Google" },
};

function OrdoLogo() {
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
    );
}

function ThirdPartyLogo({
    name,
    alt,
    className,
    size = 18,
}: {
    name: ThirdPartyLogoName;
    alt?: string;
    className?: string;
    size?: number;
}) {
    const { src, alt: defaultAlt } = LOGOS[name];
    return (
        <img
            src={src}
            alt={alt ?? defaultAlt}
            className={className}
            width={size}
            height={size}
            style={{ objectFit: "contain", flexShrink: 0 }}
            loading="eager"
            decoding="async"
        />
    );
}

export { OrdoLogo, ThirdPartyLogo };

import outlookLogo from "./assets/outlook-logo.png";
import googleLogo from "./assets/google-logo.png";

export type ThirdPartyLogoName = "outlook" | "google";

const LOGOS: Record<ThirdPartyLogoName, { src: string; alt: string }> = {
    outlook: { src: outlookLogo, alt: "Outlook" },
    google: { src: googleLogo, alt: "Google" },
};

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

export { ThirdPartyLogo };

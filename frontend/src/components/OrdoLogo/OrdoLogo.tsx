import React from "react";

interface OrdoLogoProps {
  size?: number;
  withSparkle?: boolean;
  className?: string;
}

let counter = 0;
const nextId = () => `ordo-logo-${++counter}`;

export default function OrdoLogo({
  size = 40,
  withSparkle = false,
  className,
}: OrdoLogoProps) {
  const idRef = React.useRef<string>(nextId());
  const gradId = `${idRef.current}-grad`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      className={className}
      role="img"
      aria-label="Ordo"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#60a5fa" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
      </defs>

      <rect
        x="2"
        y="5"
        width="24"
        height="21"
        rx="4"
        stroke={`url(#${gradId})`}
        strokeWidth="1.6"
      />
      <rect x="8" y="2" width="2.2" height="6" rx="1.1" fill={`url(#${gradId})`} />
      <rect x="18" y="2" width="2.2" height="6" rx="1.1" fill={`url(#${gradId})`} />

      <rect x="6" y="12.5" width="4" height="4" rx="1.1" fill={`url(#${gradId})`} fillOpacity="0.3" />
      <rect x="12" y="12.5" width="4" height="4" rx="1.1" fill={`url(#${gradId})`} />
      <rect x="18" y="12.5" width="4" height="4" rx="1.1" fill={`url(#${gradId})`} fillOpacity="0.3" />
      <rect x="6" y="18.5" width="4" height="4" rx="1.1" fill={`url(#${gradId})`} fillOpacity="0.3" />

      {withSparkle && (
        <g transform="translate(23 4)">
          <circle r="2.6" fill="#60a5fa" opacity="0.22" />
          <path
            d="M0 -1.8 L0.55 -0.55 L1.8 0 L0.55 0.55 L0 1.8 L-0.55 0.55 L-1.8 0 L-0.55 -0.55 Z"
            fill="#dbeafe"
          />
        </g>
      )}
    </svg>
  );
}

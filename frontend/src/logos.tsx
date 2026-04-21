export function OrdoLogo() {
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

export function GoogleLogo({ className = "h-10 w-10" }: { className?: string }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" className={className}>
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
            <path fill="none" d="M0 0h48v48H0z" />
        </svg>
    );
}

export function OutlookLogo({ className = "h-10 w-10" }: { className?: string }) {
    return (
        <svg viewBox="0 0 48 48" fill="none" className={className}>
            {/* Back tile */}
            <rect x="18" y="6" width="24" height="36" rx="4" fill="#0078D4" />

            {/* Envelope */}
            <rect x="6" y="12" width="28" height="24" rx="3" fill="#1A5FB4" />
            <path
                d="M6 14 L20 24 L34 14"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />

            {/* O panel */}
            <rect x="2" y="14" width="16" height="20" rx="3" fill="#005A9E" />
            <circle cx="10" cy="24" r="5" stroke="white" strokeWidth="2" />
        </svg>
    );
}

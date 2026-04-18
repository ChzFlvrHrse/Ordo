import { useCallback, useEffect, useRef, useState } from "react";

const WAKE_PHRASE = /\bhey[,!\s]+ordo\b/i;

export function useSTT() {
    const [listening, setListening] = useState(false);
    const [transcript, setTranscript] = useState("");
    const [wakeActive, setWakeActive] = useState(false);

    const mainRef = useRef<any>(null);
    const wakeRef = useRef<any>(null);
    const wakeEnabledRef = useRef(false);
    const listeningRef = useRef(false);

    useEffect(() => {
        const SpeechRecognition =
            (window as any).SpeechRecognition ||
            (window as any).webkitSpeechRecognition;

        if (!SpeechRecognition) return;

        const main = new SpeechRecognition();
        main.continuous = false;
        main.interimResults = true;
        main.lang = "en-US";

        main.onstart = () => {
            listeningRef.current = true;
            setListening(true);
            setTranscript("");
        };

        main.onresult = (event: any) => {
            let text = "";
            for (let i = 0; i < event.results.length; i++) {
                text += event.results[i][0].transcript;
            }
            setTranscript(text);
        };

        main.onerror = () => {
            listeningRef.current = false;
            setListening(false);
        };

        main.onend = () => {
            listeningRef.current = false;
            setListening(false);
            if (wakeEnabledRef.current) {
                safeStartWake();
            }
        };

        const wake = new SpeechRecognition();
        wake.continuous = true;
        wake.interimResults = true;
        wake.lang = "en-US";

        wake.onstart = () => setWakeActive(true);

        wake.onresult = (event: any) => {
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const phrase = event.results[i][0].transcript as string;
                if (WAKE_PHRASE.test(phrase)) {
                    try {
                        wake.stop();
                    } catch { }
                    try {
                        main.start();
                    } catch { }
                    return;
                }
            }
        };

        wake.onerror = (event: any) => {
            setWakeActive(false);
            if (wakeEnabledRef.current && event?.error !== "not-allowed" && event?.error !== "aborted") {
                setTimeout(safeStartWake, 400);
            }
        };

        wake.onend = () => {
            setWakeActive(false);
            if (wakeEnabledRef.current && !listeningRef.current) {
                setTimeout(safeStartWake, 100);
            }
        };

        function safeStartWake() {
            if (!wakeEnabledRef.current || listeningRef.current) return;
            try {
                wake.start();
            } catch { }
        }

        mainRef.current = main;
        wakeRef.current = wake;

        return () => {
            wakeEnabledRef.current = false;
            try { wake.stop(); } catch { }
            try { main.stop(); } catch { }
        };
    }, []);

    const start = useCallback(() => {
        try { wakeRef.current?.stop(); } catch { }
        try { mainRef.current?.start(); } catch { }
    }, []);

    const stop = useCallback(() => {
        try { mainRef.current?.stop(); } catch { }
        listeningRef.current = false;
        setListening(false);
    }, []);

    const enableWakeWord = useCallback(() => {
        wakeEnabledRef.current = true;
        if (!listeningRef.current) {
            try { wakeRef.current?.start(); } catch { }
        }
    }, []);

    const disableWakeWord = useCallback(() => {
        wakeEnabledRef.current = false;
        try { wakeRef.current?.stop(); } catch { }
        setWakeActive(false);
    }, []);

    return {
        listening,
        transcript,
        wakeActive,
        start,
        stop,
        enableWakeWord,
        disableWakeWord,
        supported: typeof window !== "undefined" &&
            !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition),
    };
}

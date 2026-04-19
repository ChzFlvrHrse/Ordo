import { useCallback, useEffect, useRef, useState } from "react";

export function useSTT() {
    const [listening, setListening] = useState(false);
    const [transcript, setTranscript] = useState("");

    const recognitionRef = useRef<any>(null);

    useEffect(() => {
        const SpeechRecognition =
            (window as any).SpeechRecognition ||
            (window as any).webkitSpeechRecognition;

        if (!SpeechRecognition) return;

        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onstart = () => {
            setListening(true);
            setTranscript("");
        };

        recognition.onresult = (event: any) => {
            let text = "";
            for (let i = 0; i < event.results.length; i++) {
                text += event.results[i][0].transcript;
            }
            setTranscript(text);
        };

        recognition.onerror = () => {
            setListening(false);
        };

        recognition.onend = () => {
            setListening(false);
        };

        recognitionRef.current = recognition;

        return () => {
            try { recognition.stop(); } catch { }
        };
    }, []);

    const start = useCallback(() => {
        try { recognitionRef.current?.start(); } catch { }
    }, []);

    const stop = useCallback(() => {
        try { recognitionRef.current?.stop(); } catch { }
        setListening(false);
    }, []);

    return {
        listening,
        transcript,
        start,
        stop,
        supported: typeof window !== "undefined" &&
            !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition),
    };
}

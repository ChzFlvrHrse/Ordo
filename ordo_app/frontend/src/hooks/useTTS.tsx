import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const ELEVENLABS_API_KEY = import.meta.env.VITE_ELEVENLABS_API_KEY as string | undefined;
const ELEVENLABS_VOICE_ID =
    (import.meta.env.VITE_ELEVENLABS_VOICE_ID as string | undefined) ??
    "JBFqnCBsd6RMkjVDRZzb";
const ELEVENLABS_MODEL_ID =
    (import.meta.env.VITE_ELEVENLABS_MODEL_ID as string | undefined) ??
    "eleven_multilingual_v2";

export function useTTS() {
    const [speakingId, setSpeakingId] = useState<string | null>(null);
    const [loadingId, setLoadingId] = useState<string | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const cacheRef = useRef<Map<string, string>>(new Map());

    const client = useMemo(() => {
        if (!ELEVENLABS_API_KEY) return null;
        return new ElevenLabsClient({ apiKey: ELEVENLABS_API_KEY });
    }, []);

    const releaseAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.src = "";
            audioRef.current = null;
        }
        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }
    }, []);

    const stop = useCallback(() => {
        releaseAudio();
        setSpeakingId(null);
        setLoadingId(null);
    }, [releaseAudio]);

    const speak = useCallback(
        async (id: string, text: string) => {
            const trimmed = text?.trim();
            if (!trimmed) return;

            if (speakingId === id || loadingId === id) {
                stop();
                return;
            }

            if (!client) {
                console.warn("VITE_ELEVENLABS_API_KEY is not set");
                return;
            }

            stop();
            setLoadingId(id);

            try {
                let url = cacheRef.current.get(trimmed);

                if (!url) {
                    const controller = new AbortController();
                    abortRef.current = controller;

                    const stream = await client.textToSpeech.convert(
                        ELEVENLABS_VOICE_ID,
                        {
                            text: trimmed,
                            modelId: ELEVENLABS_MODEL_ID,
                            outputFormat: "mp3_44100_128",
                        },
                        { abortSignal: controller.signal }
                    );

                    const blob = await new Response(stream as ReadableStream<Uint8Array>).blob();
                    url = URL.createObjectURL(new Blob([await blob.arrayBuffer()], { type: "audio/mpeg" }));
                    cacheRef.current.set(trimmed, url);
                }

                const audio = new Audio(url);
                audioRef.current = audio;

                audio.onended = () => {
                    audioRef.current = null;
                    setSpeakingId(null);
                };
                audio.onerror = () => {
                    audioRef.current = null;
                    setSpeakingId(null);
                };

                setLoadingId(null);
                setSpeakingId(id);
                await audio.play();
            } catch (err: any) {
                if (err?.name !== "AbortError") {
                    console.error("useTTS error", err);
                }
                setLoadingId(null);
                setSpeakingId(null);
            }
        },
        [client, speakingId, loadingId, stop]
    );

    useEffect(() => {
        return () => {
            releaseAudio();
            cacheRef.current.forEach((url) => URL.revokeObjectURL(url));
            cacheRef.current.clear();
        };
    }, [releaseAudio]);

    return {
        speakingId,
        loadingId,
        speak,
        stop,
    };
}

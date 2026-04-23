import React, { useRef, useEffect, useState } from "react";
import { Check, Copy, Mic, Send, Square, Volume2, X } from "lucide-react";
import toast from "react-hot-toast";
import { useTTS } from "../../hooks/useTTS";
import { useSTT } from "../../hooks/useSTT";
import { Message } from "../../hooks/useAgent";
import ReactMarkdown from "react-markdown";
import OrdoLogo from "../OrdoLogo/OrdoLogo";
import "./AgentChat.css";

interface AgentChatProps {
    messages: Message[];
    loading: boolean;
    error: string | null;
    onSend: (text: string) => void;
}

const QUICK_PROMPTS = [
    "What's on my schedule?",
    "Any conflicts this week?",
    "Book a meeting tomorrow",
];

export default function AgentChat({ messages, loading, error, onSend }: AgentChatProps) {
    const [open, setOpen] = useState(false);
    const [input, setInput] = useState("");
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    const { speak, stop: stopSpeaking, speakingId } = useTTS();
    const { listening, transcript, start, stop: stopListening } = useSTT();
    const wasListening = useRef(false);

    useEffect(() => {
        if (open) {
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages, loading, open]);

    useEffect(() => {
        if (transcript) setInput(transcript);
    }, [transcript]);

    useEffect(() => {
        if (wasListening.current && !listening) {
            const text = transcript.trim();
            if (text && !loading) {
                setInput("");
                onSend(text);
            }
        }
        wasListening.current = listening;
    }, [listening, transcript, loading, onSend]);

    const handleCopy = async (content: string, index: number) => {
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(content);
            } else {
                const ta = document.createElement("textarea");
                ta.value = content;
                ta.setAttribute("readonly", "");
                ta.style.position = "absolute";
                ta.style.left = "-9999px";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
            }

            setCopiedIndex(index);
            setTimeout(() => {
                setCopiedIndex((curr) => (curr === index ? null : curr));
            }, 1500);
        } catch {
            toast.error("Could not copy message");
        }
    };

    const handleSend = () => {
        const text = input.trim();
        if (!text || loading) return;
        setInput("");
        onSend(text);
    };

    const handleKey = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleMicClick = () => {
        if (listening) {
            stopListening();
            return;
        }
        start();
    };

    const handleQuickPrompt = (prompt: string) => {
        if (loading) return;
        onSend(prompt);
    };

    return (
        <div className="ordo-widget">
            {!open ? (
                <button
                    type="button"
                    className="ordo-widget-pill"
                    onClick={() => setOpen(true)}
                    aria-label="Open Ordo"
                >
                    <div className="ordo-widget-avatar" aria-hidden="true">
                        <OrdoLogo size={40} withSparkle={false} className="ordo-widget-avatar-img" />
                    </div>
                    <div className="ordo-widget-pill-text">
                        <div className="ordo-widget-pill-title">Ordo</div>
                        <div className="ordo-widget-pill-sub">Ask me anything</div>
                    </div>
                </button>
            ) : (
                <div className="ordo-widget-panel" role="dialog" aria-label="Ordo assistant">
                    <div className="ordo-widget-header">
                        <div className="ordo-widget-brand">
                            <div className="ordo-widget-avatar ordo-widget-avatar--sm" aria-hidden="true">
                                <OrdoLogo size={28} withSparkle={false} className="ordo-widget-avatar-img" />
                            </div>
                            <span>Ordo</span>
                        </div>
                        <button
                            type="button"
                            className="ordo-widget-close"
                            onClick={() => setOpen(false)}
                            aria-label="Close Ordo"
                        >
                            <X size={16} />
                        </button>
                    </div>

                    <div className="ordo-widget-body">
                        {messages.length === 0 && !loading && (
                            <div className="agent-empty">
                                <p>Ask me anything about your calendar.</p>
                                <div className="quick-prompts">
                                    {QUICK_PROMPTS.map((p) => (
                                        <button
                                            key={p}
                                            type="button"
                                            className="quick-prompt"
                                            onClick={() => handleQuickPrompt(p)}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {messages.map((msg, i) => {
                            const isAssistant = msg.role === "assistant";
                            const messageTtsId = `${i}-${msg.role}-${msg.content.slice(0, 40)}`;
                            const isSpeaking = speakingId === messageTtsId;

                            return (
                                <div key={i} className={`message message--${msg.role}`}>
                                    <div className="message-bubble">
                                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                                    </div>

                                    <div className="message-actions">
                                        <button
                                            type="button"
                                            className="message-copy-btn"
                                            onClick={() => handleCopy(msg.content, i)}
                                            aria-label={copiedIndex === i ? "Copied" : "Copy message"}
                                            title={copiedIndex === i ? "Copied" : "Copy message"}
                                        >
                                            {copiedIndex === i ? <Check size={12} /> : <Copy size={12} />}
                                        </button>

                                        {isAssistant && (
                                            <button
                                                type="button"
                                                className="message-tts-btn"
                                                onClick={() =>
                                                    isSpeaking
                                                        ? stopSpeaking()
                                                        : speak(messageTtsId, msg.content)
                                                }
                                                aria-label={isSpeaking ? "Stop speaking" : "Read message aloud"}
                                                title={isSpeaking ? "Stop speaking" : "Read message aloud"}
                                            >
                                                {isSpeaking ? <Square size={12} /> : <Volume2 size={12} />}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}

                        {loading && (
                            <div className="message message--assistant">
                                <div className="message-bubble message-bubble--loading">
                                    <span /><span /><span />
                                </div>
                            </div>
                        )}

                        {error && <div className="agent-error">{error}</div>}
                        <div ref={bottomRef} />
                    </div>

                    <div className="ordo-widget-input-area">
                        <div className="ordo-widget-input-row">
                            <textarea
                                className="ordo-widget-input"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKey}
                                placeholder="Ask Ordo…"
                                rows={1}
                            />

                            <button
                                type="button"
                                className={`ordo-widget-icon-btn${listening ? " listening" : ""}`}
                                onClick={handleMicClick}
                                aria-label={listening ? "Stop listening" : "Speak into microphone"}
                                title={listening ? "Stop listening" : "Speak into microphone"}
                            >
                                {listening ? <Square size={14} /> : <Mic size={14} />}
                            </button>

                            <button
                                type="button"
                                className="ordo-widget-send"
                                onClick={handleSend}
                                disabled={loading || !input.trim()}
                                aria-label="Send message"
                            >
                                <Send size={14} />
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

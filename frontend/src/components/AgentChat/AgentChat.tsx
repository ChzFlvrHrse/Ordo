import React, { useRef, useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import toast from "react-hot-toast";
import { Message } from "../../hooks/useAgent";
import ReactMarkdown from "react-markdown";
import "./AgentChat.css";

interface AgentChatProps {
    messages: Message[];
    loading: boolean;
    error: string | null;
    onSend: (text: string) => void;
}

function ordoAgent() {
    return (
        <svg width="24" height="24" viewBox="0 0 28 28" fill="none" stroke="#6ee7b7" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="10" width="20" height="14" rx="4" />
            <circle cx="10" cy="17" r="1.5" fill="#6ee7b7" stroke="none" />
            <circle cx="18" cy="17" r="1.5" fill="#6ee7b7" stroke="none" />
            <path d="M14 10V6" />
            <circle cx="14" cy="5" r="1.5" />
            <path d="M1 15h3M24 15h3" />
        </svg>
    )
}

const QUICK_PROMPTS = [
    "What's on my schedule?",
    "Any conflicts this week?",
    "Book a meeting tomorrow",
];

const CHIPS = ["Today's schedule", "Check conflicts", "Teli bookings"];

export default function AgentChat({ messages, loading, error, onSend }: AgentChatProps) {
    const [input, setInput] = useState("");
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

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

    return (
        <div className="agent-chat">
            <div className="agent-header">
                <div className="agent-header-left">
                    <div className="agent-icon">
                        {ordoAgent()}
                    </div>
                    <div>
                        <div className="agent-name">Say Hello to Ordo!</div>
                        <div className="agent-sub">I'm here to help you manage your schedule proactively</div>
                    </div>
                </div>
                <button className="agent-collapse-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M9 3v18" />
                    </svg>
                </button>
            </div>

            <div className="agent-stats">
                {[["7", "This week"], ["3", "By agents"], ["1", "Pending"]].map(([num, label]) => (
                    <div key={label} className="agent-stat">
                        <div className="agent-stat-num">{num}</div>
                        <div className="agent-stat-label">{label}</div>
                    </div>
                ))}
            </div>

            <div className="agent-messages">
                {messages.length === 0 && !loading && (
                    <div className="agent-empty">
                        <p>Ask me anything about your calendar.</p>
                        <div className="quick-prompts">
                            {QUICK_PROMPTS.map((p) => (
                                <button key={p} className="quick-prompt" onClick={() => onSend(p)}>
                                    {p}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`message message--${msg.role}`}>
                        <div className="message-bubble">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        <button
                            type="button"
                            className="message-copy-btn"
                            onClick={() => handleCopy(msg.content, i)}
                            aria-label={copiedIndex === i ? "Copied" : "Copy message"}
                            title={copiedIndex === i ? "Copied" : "Copy message"}
                        >
                            {copiedIndex === i ? <Check size={12} /> : <Copy size={12} />}
                        </button>
                    </div>
                ))}

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

            <div className="agent-chips">
                {CHIPS.map((chip) => (
                    <button key={chip} className="agent-chip" onClick={() => onSend(chip)}>
                        {chip}
                    </button>
                ))}
            </div>

            <div className="agent-input-area">
                <div className="agent-input-inner">
                    <div className="agent-input-label">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
                        </svg>
                        Ask Ordo anything
                    </div>
                    <div className="agent-input-row">
                        <textarea
                            className="agent-input"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKey}
                            placeholder="Move Friday's calls to the afternoon…"
                            rows={1}
                        />
                        <button
                            className="agent-send"
                            onClick={handleSend}
                            disabled={loading || !input.trim()}
                        >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 19V5M5 12l7-7 7 7" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

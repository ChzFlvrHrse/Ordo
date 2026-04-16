import React, { useRef, useEffect, useState } from "react";
import { Message } from "../../hooks/useAgent";
import ReactMarkdown from "react-markdown";
import './AgentsChat.css';

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
    const [input, setInput] = useState("");
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

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
                <div className="agent-status">
                    <span className="status-dot" />
                    <span className="agent-name">Ordo</span>
                </div>
                <span className="agent-sub">Your calendar agent</span>
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
                    </div>
                ))}

                {loading && (
                    <div className="message message--assistant">
                        <div className="message-bubble message-bubble--loading">
                            <span /><span /><span />
                        </div>
                    </div>
                )}

                {error && (
                    <div className="agent-error">{error}</div>
                )}

                <div ref={bottomRef} />
            </div>

            <div className="agent-input-row">
                <textarea
                    className="agent-input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder="Ask Ordo anything..."
                    rows={1}
                />
                <button
                    className="agent-send"
                    onClick={handleSend}
                    disabled={loading || !input.trim()}
                >
                    <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M2 8h12M8 2l6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </button>
            </div>
        </div>
    );
}

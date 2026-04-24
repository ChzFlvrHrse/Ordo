import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "./Callback.css";

export default function Callback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Connecting your calendar...");

  useEffect(() => {
    const calendarParam = searchParams.get("calendar");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setMessage("Google declined the connection. Please try again.");
      return;
    }

    if (calendarParam === "connected") {
      setStatus("success");
      setMessage("Calendar connected successfully.");
      setTimeout(() => navigate("/"), 1500);
      return;
    }

    // Fallback — just redirect home
    navigate("/");
  }, [searchParams, navigate]);

  return (
    <div className="callback">
      <div className="callback-card">
        {status === "loading" && (
          <div className="callback-spinner" />
        )}
        {status === "success" && (
          <div className="callback-icon callback-icon--success">✓</div>
        )}
        {status === "error" && (
          <div className="callback-icon callback-icon--error">✕</div>
        )}
        <p className="callback-message">{message}</p>
        {status === "error" && (
          <button className="callback-btn" onClick={() => navigate("/")}>
            Go back
          </button>
        )}
      </div>
    </div>
  );
}

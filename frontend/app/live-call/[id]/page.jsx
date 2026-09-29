"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SLOT_LABELS = [
  ["requirement", "Requirement"],
  ["capacity", "Capacity"],
  ["location", "Location"],
  ["budget", "Budget"],
  ["timeline", "Timeline"],
  ["customer_name", "Customer"],
  ["company", "Company"],
  ["application", "Application"],
];

export default function LiveCallPage() {
  const { id } = useParams();
  const [messages, setMessages] = useState([]);
  const [slots, setSlots] = useState({});
  const [phase, setPhase] = useState("…");
  const [status, setStatus] = useState("connecting");
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [micOn, setMicOn] = useState(true);
  const [error, setError] = useState("");
  const [interimText, setInterimText] = useState("");
  const [call, setCall] = useState(null);
  const [textInput, setTextInput] = useState("");

  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const micOnRef = useRef(true);
  const endedRef = useRef(false);
  const speakingRef = useRef(false);
  const utteranceRef = useRef(null);

  const addMessage = useCallback((speaker, text) => {
    setMessages((prev) => [...prev, { speaker, text }]);
  }, []);

  const stopSpeaking = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    speakingRef.current = false;
    utteranceRef.current = null;
    setAgentSpeaking(false);
  }, []);

  const speak = useCallback((text) => {
    if (!("speechSynthesis" in window)) return;
    stopSpeaking();
    speakingRef.current = true;
    setAgentSpeaking(true);
    const utterance = new SpeechSynthesisUtterance(text);
    utteranceRef.current = utterance;
    utterance.lang = "en-IN";
    utterance.rate = 1.02;
    utterance.onend = () => {
      speakingRef.current = false;
      utteranceRef.current = null;
      setAgentSpeaking(false);
    };
    utterance.onerror = () => {
      speakingRef.current = false;
      utteranceRef.current = null;
      setAgentSpeaking(false);
    };
    window.speechSynthesis.speak(utterance);
  }, [stopSpeaking]);

  // ── mic: Web Speech API ────────────────────────────────────────────────────
  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setError("Web SpeechRecognition is not supported in this browser (use Google Chrome). You can type in the box below to chat.");
      return undefined;
    }
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = typeof navigator !== "undefined" && navigator.language ? navigator.language : "en-US";

    recognition.onresult = (event) => {
      if (!micOnRef.current || endedRef.current) return;
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          const text = result[0].transcript.trim();
          if (!text) continue;
          setInterimText("");
          // barge-in: customer starts talking while the agent speaks
          if (speakingRef.current) {
            stopSpeaking();
            wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
          }
          addMessage("customer", text);
          wsRef.current?.send(
            JSON.stringify({ type: "customer_speech", text, confidence: result[0].confidence ?? null })
          );
        } else {
          interim += result[0].transcript;
        }
      }
      if (interim) {
        setInterimText(interim);
        if (speakingRef.current) {
          stopSpeaking();
          wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
        }
      }
    };

    recognition.onend = () => {
      setInterimText("");
      if (micOnRef.current && !endedRef.current) {
        setTimeout(() => {
          if (micOnRef.current && !endedRef.current) {
            try {
              recognition.start();
            } catch {
              /* already running */
            }
          }
        }, 150);
      }
    };

    recognition.onerror = (e) => {
      console.warn("Speech recognition error:", e.error);
      if (e.error === "not-allowed") {
        setError("Microphone access was denied. Please allow microphone permissions in Chrome (click the lock icon in the address bar) and click the microphone button.");
        setMicOn(false);
        micOnRef.current = false;
      } else if (e.error === "audio-capture") {
        setError("No microphone detected. Please check that your microphone is plugged in and selected in system settings.");
      } else if (e.error === "network") {
        setError("Chrome speech recognition network error. Please check your internet connection or use the text box below.");
      }
      if (wsRef.current?.readyState === WebSocket.OPEN && e.error !== "no-speech") {
        wsRef.current.send(JSON.stringify({ type: "stt_failure", detail: { error: e.error } }));
      }
    };

    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(() => {
          try {
            recognition.start();
          } catch {}
        })
        .catch((err) => {
          console.warn("Microphone permission prompt error:", err);
          setError("Microphone permission needed: Please click 'Allow' when prompted or click the lock icon in Chrome to enable the microphone.");
        });
    } else {
      try {
        recognition.start();
      } catch {}
    }

    recognitionRef.current = recognition;
    return () => {
      recognition.onend = null;
      try {
        recognition.stop();
      } catch {
        /* ignore */
      }
      recognitionRef.current = null;
    };
  }, [addMessage, stopSpeaking]);

  // ── websocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("token") || sessionStorage.getItem("token")
        : null;

    if (!token && typeof window !== "undefined") {
      window.location.href = "/login";
      return;
    }
    fetch(`${API}/calls/${id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then((data) => !cancelled && setCall(data))
      .catch(() => {});

    const wsBase = API.replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/ws/call/${id}?token=${encodeURIComponent(token || "")}`);
    wsRef.current = ws;

    ws.onopen = () => setStatus("live");
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      switch (message.type) {
        case "agent_reply":
          addMessage("agent", message.text);
          speak(message.text);
          break;
        case "state_update":
          setSlots(message.slots || {});
          setPhase(message.phase || "…");
          break;
        case "call_status":
          setStatus(message.status);
          endedRef.current = true;
          stopSpeaking();
          break;
        case "error":
          setError(message.detail);
          break;
        default:
          break;
      }
    };
    ws.onclose = () => {
      if (!endedRef.current) setStatus("closed");
    };
    ws.onerror = () => setError("WebSocket error");

    return () => {
      cancelled = true;
      endedRef.current = true;
      stopSpeaking();
      try {
        ws.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    };
  }, [id, addMessage, speak, stopSpeaking]);

  async function toggleMic() {
    const next = !micOn;
    micOnRef.current = next;
    setMicOn(next);
    setError("");
    if (!next) {
      try {
        recognitionRef.current?.stop();
      } catch {
        /* ignore */
      }
    } else if (!endedRef.current) {
      try {
        if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
          await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => {});
        }
        recognitionRef.current?.start();
      } catch (err) {
        console.warn("Could not start recognition:", err);
      }
    }
  }

  function endCall() {
    wsRef.current?.send(JSON.stringify({ type: "end_call" }));
    endedRef.current = true;
    stopSpeaking();
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
  }

  function handleSendText(e) {
    e.preventDefault();
    if (!textInput.trim() || endedRef.current) return;
    if (speakingRef.current) {
      stopSpeaking();
      wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
    }
    const txt = textInput.trim();
    addMessage("customer", txt);
    wsRef.current?.send(JSON.stringify({ type: "customer_speech", text: txt, confidence: 1.0 }));
    setTextInput("");
  }

  const connected = status === "live" || status === "in_progress";

  // Display state only — the logic above still reads from the refs.
  let statusLabel = "Connecting";
  let ringClass = "is-connecting";
  if (endedRef.current || status === "completed" || status === "disconnected" || status === "failed") {
    statusLabel = "Call ended";
    ringClass = "is-ended";
  } else if (status === "closed") {
    statusLabel = "Disconnected";
    ringClass = "is-ended";
  } else if (agentSpeaking) {
    statusLabel = "Agent speaking";
    ringClass = "is-speaking";
  } else if (connected) {
    statusLabel = micOn ? "Listening" : "Mic muted";
    ringClass = micOn ? "is-listening" : "";
  }

  const filledCount = Object.values(slots).filter(Boolean).length;

  return (
    <main className="live-page">
      <section className="card live-status-card" aria-live="polite">
        <div className="live-status">
          <span className={`live-ring ${ringClass}`} aria-hidden="true" />
          {statusLabel}
        </div>
        <p className="live-status-meta">
          {call ? `${call.phone_number} · ` : ""}
          phase {phase} · {filledCount}/{SLOT_LABELS.length} details captured
        </p>

        <div className="live-controls">
          <div>
            <button
              type="button"
              className={`mic-btn ${micOn && !endedRef.current ? "is-live" : "is-muted"}`}
              onClick={toggleMic}
              disabled={endedRef.current}
              aria-pressed={micOn}
              aria-label={micOn ? "Mute microphone" : "Unmute microphone"}
            >
              {micOn ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" />
                  <path d="M5 11a7 7 0 0 0 14 0" />
                  <path d="M12 18v3" />
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M15 9.34V6a3 3 0 0 0-5.68-1.33" />
                  <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
                  <path d="M5 11a7 7 0 0 0 10.06 6.27" />
                  <path d="M19 11a7 7 0 0 1-.4 2.27" />
                  <path d="M12 18v3" />
                  <path d="M1 1l22 22" />
                </svg>
              )}
            </button>
            <p className="mic-caption">{micOn ? "Listening" : "Muted"}</p>
            {interimText ? (
              <p style={{ fontSize: 13, color: "var(--accent)", marginTop: 6, fontStyle: "italic", maxWidth: 220 }}>
                Hearing: &ldquo;{interimText}&rdquo;
              </p>
            ) : null}
          </div>

          <div>
            <button
              type="button"
              className="btn btn-danger"
              onClick={endCall}
              disabled={endedRef.current}
              style={{ minWidth: 140, minHeight: 48 }}
            >
              End call
            </button>
            <p className="mic-caption">
              {endedRef.current ? (
                <Link href={`/calls/${id}`}>View call summary →</Link>
              ) : (
                "Hangs up and saves the summary"
              )}
            </p>
          </div>
        </div>

        <p className="live-hint">Use Chrome and allow microphone access — or type below.</p>
      </section>

      {error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : null}

      <section className="card" aria-label="Collected details">
        <div className="card-head">
          <h2 className="card-title">Captured so far</h2>
          <span className="cell-muted num" style={{ fontSize: 13 }}>
            {filledCount}/{SLOT_LABELS.length}
          </span>
        </div>
        <div className="chips">
          {SLOT_LABELS.map(([key, label]) => (
            <span key={key} className={`chip ${slots[key] ? "is-filled" : ""}`} title={slots[key] || undefined}>
              <b>{label}</b>
              <span className="chip-val">{slots[key] || "—"}</span>
            </span>
          ))}
        </div>
      </section>

      <section className="card" aria-label="Live transcript">
        <div className="card-head">
          <h2 className="card-title">Transcript</h2>
          <span className="cell-muted" style={{ fontSize: 13 }}>
            {messages.length} messages
          </span>
        </div>

        <div className="live-transcript" aria-live="polite" aria-relevant="additions">
          {messages.length === 0 ? (
            <p className="card-sub" style={{ textAlign: "center", marginTop: 24 }}>
              Waiting for the agent to pick up…
            </p>
          ) : (
            messages.map((m, index) => (
              <div key={index} className={`bubble bubble-${m.speaker}`}>
                <div className="bubble-meta">
                  <span className="bubble-speaker">{m.speaker}</span>
                </div>
                {m.text}
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleSendText} className="live-composer">
          <input
            className="input"
            placeholder={endedRef.current ? "Call ended" : "Type a reply instead of speaking…"}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            disabled={endedRef.current}
            aria-label="Type a reply"
          />
          <button type="submit" className="btn" disabled={endedRef.current || !textInput.trim()}>
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

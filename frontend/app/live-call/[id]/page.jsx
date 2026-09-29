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
      setError("Web SpeechRecognition is not supported in this browser (use Chrome). Text chat fallback is available below.");
      return undefined;
    }
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-IN";

    recognition.onresult = (event) => {
      if (!micOnRef.current || endedRef.current) return;
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result.isFinal) continue;
        const text = result[0].transcript.trim();
        if (!text) continue;
        // barge-in: customer starts talking while the agent speaks
        if (speakingRef.current) {
          stopSpeaking();
          wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
        }
        addMessage("customer", text);
        wsRef.current?.send(
          JSON.stringify({ type: "customer_speech", text, confidence: result[0].confidence ?? null })
        );
      }
    };
    recognition.onend = () => {
      if (micOnRef.current && !endedRef.current) {
        try {
          recognition.start();
        } catch {
          /* already running */
        }
      }
    };
    recognition.onerror = (e) => {
      if (wsRef.current?.readyState === WebSocket.OPEN && e.error !== "no-speech") {
        wsRef.current.send(JSON.stringify({ type: "stt_failure", detail: { error: e.error } }));
      }
    };
    try {
      recognition.start();
    } catch {
      /* ignore */
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

  function toggleMic() {
    const next = !micOn;
    micOnRef.current = next;
    setMicOn(next);
    if (!next) {
      try {
        recognitionRef.current?.stop();
      } catch {
        /* ignore */
      }
    } else if (!endedRef.current) {
      try {
        recognitionRef.current?.start();
      } catch {
        /* ignore */
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

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <h1>Live Outbound Call</h1>
          <p className="sub">
            {call ? `${call.phone_number} · ` : ""}
            <span className="phase">{status}</span> · phase <span className="phase">{phase}</span>
          </p>
        </div>
        {endedRef.current || status === "completed" || status === "disconnected" ? (
          <Link href={`/calls/${id}`} className="btn">
            View Call Summary & intelligence →
          </Link>
        ) : null}
      </div>

      <div className="card">
        <div className="statusbar">
          <span className={`dot ${connected ? "live" : ""}`} />
          <span>{connected ? "connected" : status}</span>
          <span className={`dot ${agentSpeaking ? "speaking" : ""}`} />
          <span>{agentSpeaking ? "agent speaking…" : "agent idle"}</span>
          <span className={`dot ${micOn ? "live" : ""}`} />
          <span>{micOn ? "mic on" : "mic muted"}</span>
          <div className="controls" style={{ marginLeft: "auto" }}>
            <button className="secondary" style={{ marginTop: 0 }} onClick={toggleMic} disabled={endedRef.current}>
              {micOn ? "Mute Mic" : "Unmute Mic"}
            </button>
            <button className="danger" style={{ marginTop: 0 }} onClick={endCall} disabled={endedRef.current}>
              End Call
            </button>
          </div>
        </div>
        {error ? <div className="error">{error}</div> : null}
      </div>

      <div className="card">
        <strong>Live Extracted Qualification Slots</strong>
        <div className="slots">
          {SLOT_LABELS.map(([key, label]) => (
            <div key={key} className={`slot ${slots[key] ? "filled" : ""}`}>
              <b>{label}</b>
              {slots[key] || "—"}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <strong>Live Transcript & Conversation</strong>
        <div className="transcript" style={{ marginTop: 10 }}>
          {messages.length === 0 ? <span className="sub">Waiting for the agent…</span> : null}
          {messages.map((m, index) => (
            <div key={index} className={`msg ${m.speaker}`}>
              <span className="speaker">{m.speaker}</span>
              {m.text}
            </div>
          ))}
        </div>

        {/* Text chat backup for mic-free testing */}
        <form onSubmit={handleSendText} style={{ display: "flex", gap: "8px", marginTop: 14 }}>
          <input
            placeholder={endedRef.current ? "Call ended." : "Type a response (or speak into your mic)…"}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            disabled={endedRef.current}
          />
          <button type="submit" style={{ marginTop: 0 }} disabled={endedRef.current || !textInput.trim()}>
            Send
          </button>
        </form>
      </div>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

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

  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const micOnRef = useRef(true);
  const endedRef = useRef(false);
  const speakingRef = useRef(false);

  const addMessage = useCallback((speaker, text) => {
    setMessages((prev) => [...prev, { speaker, text }]);
  }, []);

  const speak = useCallback((text) => {
    if (!("speechSynthesis" in window)) return;
    speakingRef.current = true;
    setAgentSpeaking(true);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 1.02;
    utterance.onend = () => {
      speakingRef.current = false;
      setAgentSpeaking(false);
    };
    utterance.onerror = () => {
      speakingRef.current = false;
      setAgentSpeaking(false);
    };
    window.speechSynthesis.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    speakingRef.current = false;
    setAgentSpeaking(false);
  }, []);

  // ── mic: Web Speech API ────────────────────────────────────────────────────
  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setError("This browser has no SpeechRecognition (use Chrome). Typing still works.");
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
          /* already starting */
        }
      }
    };
    recognition.onerror = () => {
      /* permission/network hiccups — onend restarts */
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

    const token = sessionStorage.getItem("token");
    fetch(`${API}/calls/${id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then((data) => !cancelled && setCall(data))
      .catch(() => {});

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://localhost:8000/ws/call/${id}`);
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
        recognitionRef.current?.stop(); // onend must not restart while muted
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

  const connected = status === "live" || status === "in_progress";

  return (
    <main className="container">
      <h1>Live call</h1>
      <p className="sub">
        {call ? `${call.phone_number} · ` : ""}
        <span className="phase">{status}</span> · phase <span className="phase">{phase}</span>
      </p>

      <div className="card">
        <div className="statusbar">
          <span className={`dot ${connected ? "live" : ""}`} />
          <span>{connected ? "connected" : status}</span>
          <span className={`dot ${agentSpeaking ? "speaking" : ""}`} />
          <span>{agentSpeaking ? "agent speaking…" : "agent idle"}</span>
          <span className="dot live" />
          <span>{micOn ? "mic on" : "mic muted"}</span>
          <div className="controls" style={{ marginLeft: "auto" }}>
            <button className="secondary" onClick={toggleMic} disabled={endedRef.current}>
              {micOn ? "Mute" : "Unmute"}
            </button>
            <button className="danger" onClick={endCall} disabled={endedRef.current}>
              End call
            </button>
          </div>
        </div>
        {error ? <div className="error">{error}</div> : null}
      </div>

      <div className="card">
        <strong>Extracted data</strong>
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
        <strong>Transcript</strong>
        <div className="transcript" style={{ marginTop: 10 }}>
          {messages.length === 0 ? <span className="sub">Waiting for the agent…</span> : null}
          {messages.map((m, index) => (
            <div key={index} className={`msg ${m.speaker}`}>
              <span className="speaker">{m.speaker}</span>
              {m.text}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";

function formatDuration(sec) {
  if (sec == null || isNaN(sec)) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const SLOT_KEYS = [
  ["customer_name", "Customer Name"],
  ["company_name", "Company"],
  ["requirement", "Requirement"],
  ["ro_capacity_lph", "RO Capacity (LPH)"],
  ["location", "Installation Location"],
  ["application", "Application"],
  ["budget", "Budget"],
  ["timeline", "Timeline"],
  ["additional_requirements", "Additional Requirements"],
];

export default function CallDetailPage() {
  const { id } = useParams();
  const [call, setCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadCall() {
      setLoading(true);
      setError("");
      try {
        const res = await apiFetch(`/calls/${id}`);
        if (!res.ok) throw new Error(`Could not load call details (${res.status})`);
        const data = await res.json();
        setCall(data);
      } catch (err) {
        setError(err.message || "Failed to load call details");
      } finally {
        setLoading(false);
      }
    }
    loadCall();
  }, [id]);

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <Link href="/calls" style={{ color: "var(--accent)", fontSize: 13, textDecoration: "none" }}>
            ← Back to Call History
          </Link>
          <h1 style={{ marginTop: 6 }}>Call Intelligence Detail</h1>
          <p className="sub">Call UUID: <code>{id}</code></p>
        </div>
        {call && call.status === "in_progress" ? (
          <Link href={`/live-call/${id}`} className="btn">Join Live Session →</Link>
        ) : null}
      </div>

      {loading && (
        <div className="card">
          <p className="sub">Loading call information…</p>
        </div>
      )}

      {error && !loading && (
        <div className="card">
          <div className="error">{error}</div>
        </div>
      )}

      {!loading && !error && !call && (
        <div className="card">
          <p className="sub">Call not found.</p>
        </div>
      )}

      {!loading && !error && call && (
        <>
          {/* Call Info Card */}
          <div className="card">
            <h2>Call Information</h2>
            <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", alignItems: "center", marginTop: 12 }}>
              <div>
                <span className="stat-label">Phone</span>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{call.phone_number}</div>
              </div>
              <div>
                <span className="stat-label">Customer</span>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{call.contact_name || "Unassigned"}</div>
              </div>
              <div>
                <span className="stat-label">Status</span>
                <div><span className={`badge ${call.status}`}>{call.status}</span></div>
              </div>
              <div>
                <span className="stat-label">Direction</span>
                <div style={{ fontSize: 13, textTransform: "capitalize" }}>{call.direction}</div>
              </div>
              <div>
                <span className="stat-label">Duration</span>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{formatDuration(call.duration_seconds)}</div>
              </div>
              <div>
                <span className="stat-label">Outcome</span>
                <div>{call.outcome ? <span className={`badge ${call.outcome}`}>{call.outcome}</span> : "—"}</div>
              </div>
              <div>
                <span className="stat-label">Lead Status</span>
                <div><span className={`badge ${call.lead_status}`}>{call.lead_status}</span></div>
              </div>
              <div>
                <span className="stat-label">Follow-up</span>
                <div style={{ fontWeight: 600, color: call.followup_required ? "var(--warning)" : "var(--muted)" }}>
                  {call.followup_required ? "Yes (Required)" : "No"}
                </div>
              </div>
              <div>
                <span className="stat-label">Created At</span>
                <div style={{ fontSize: 13 }}>{new Date(call.created_at).toLocaleString()}</div>
              </div>
              {call.start_time ? (
                <div>
                  <span className="stat-label">Started At</span>
                  <div style={{ fontSize: 13 }}>{new Date(call.start_time).toLocaleTimeString()}</div>
                </div>
              ) : null}
              {call.end_time ? (
                <div>
                  <span className="stat-label">Ended At</span>
                  <div style={{ fontSize: 13 }}>{new Date(call.end_time).toLocaleTimeString()}</div>
                </div>
              ) : null}
            </div>
          </div>

          {/* AI Summary Card (Handles missing summary gracefully) */}
          <div className="card">
            <h2>AI Post-Call Summary</h2>
            {call.summary ? (
              <>
                <p style={{ fontSize: 15, lineHeight: 1.5, marginTop: 8, color: "var(--text)" }}>
                  {call.summary.summary}
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: 16 }}>
                  <div>
                    <strong style={{ fontSize: 13, color: "var(--accent)" }}>Customer Intent:</strong>
                    <p style={{ fontSize: 13, margin: "4px 0" }}>{call.summary.customer_intent || "—"}</p>

                    {Array.isArray(call.summary.key_requirements) && call.summary.key_requirements.length > 0 && (
                      <>
                        <strong style={{ fontSize: 13, color: "var(--accent)", display: "block", marginTop: 12 }}>
                          Key Requirements:
                        </strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 13 }}>
                          {call.summary.key_requirements.map((req, i) => (
                            <li key={i}>{req}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>

                  <div>
                    {Array.isArray(call.summary.followup_actions) && call.summary.followup_actions.length > 0 && (
                      <>
                        <strong style={{ fontSize: 13, color: "var(--accent)" }}>Follow-up Actions:</strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 13 }}>
                          {call.summary.followup_actions.map((act, i) => (
                            <li key={i}>{act}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {Array.isArray(call.summary.important_points) && call.summary.important_points.length > 0 && (
                      <>
                        <strong style={{ fontSize: 13, color: "var(--accent)", display: "block", marginTop: 12 }}>
                          Important Points:
                        </strong>
                        <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 13, color: "var(--muted)" }}>
                          {call.summary.important_points.map((pt, i) => (
                            <li key={i}>{pt}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <p className="sub" style={{ marginTop: 8 }}>
                No summary generated yet. (Call is currently <code>{call.status}</code>).
              </p>
            )}
          </div>

          {/* Requirements Card (9 Slots) */}
          <div className="card">
            <h2>Qualification Requirements (9 Slots)</h2>
            <div className="slots" style={{ marginTop: 12 }}>
              {SLOT_KEYS.map(([key, label]) => {
                const val = call.extracted_data?.[key];
                return (
                  <div key={key} className={`slot ${val ? "filled" : ""}`}>
                    <b>{label}</b>
                    <span>{val || "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Chat-Style Transcript */}
          <div className="card">
            <h2>Call Transcript ({call.turns?.length || 0} turns)</h2>
            <div className="transcript" style={{ marginTop: 12 }}>
              {!call.turns || call.turns.length === 0 ? (
                <p className="sub">No turns recorded for this call.</p>
              ) : (
                call.turns.map((t) => (
                  <div key={t.turn_index} className={`msg ${t.speaker}`}>
                    <span className="speaker">
                      {t.speaker} · Turn #{t.turn_index}
                      {t.confidence != null ? ` · ${(t.confidence * 100).toFixed(0)}% conf` : ""}
                    </span>
                    {t.message}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Events Log List */}
          <div className="card">
            <h2>Audit & Error Events Log</h2>
            {!call.events || call.events.length === 0 ? (
              <p className="sub">No events logged.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Event Type</th>
                      <th>Event Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {call.events.map((ev, i) => (
                      <tr key={i}>
                        <td style={{ whiteSpace: "nowrap" }}>{new Date(ev.created_at).toLocaleTimeString()}</td>
                        <td><code>{ev.event_type}</code></td>
                        <td>{ev.detail ? JSON.stringify(ev.detail) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}

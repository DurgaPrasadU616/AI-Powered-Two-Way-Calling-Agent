"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";
import { formatDuration, formatDate, formatTime } from "../../../lib/format";
import Card from "../../../components/ui/Card";
import Badge from "../../../components/ui/Badge";
import Button from "../../../components/ui/Button";
import Alert from "../../../components/ui/Alert";
import EmptyState from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { IconArrowLeft, IconInbox } from "../../../components/ui/Icons";

const SLOT_KEYS = [
  ["customer_name", "Customer name"],
  ["company_name", "Company"],
  ["requirement", "Requirement"],
  ["ro_capacity_lph", "RO capacity"],
  ["location", "Location"],
  ["application", "Application"],
  ["budget", "Budget"],
  ["timeline", "Timeline"],
  ["additional_requirements", "Additional notes"],
];

function KeyValue({ label, value, empty = "Not provided" }) {
  const has = value !== null && value !== undefined && String(value).trim() !== "";
  return (
    <div className="kv-row">
      <span className="kv-key">{label}</span>
      <span className={`kv-val ${has ? "" : "empty-val"}`}>{has ? String(value) : empty}</span>
    </div>
  );
}

export default function CallDetailPage() {
  const { id } = useParams();
  const [call, setCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadCall = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/calls/${id}`);
      if (!res.ok) throw new Error(`Could not load this call (${res.status})`);
      const data = await res.json();
      setCall(data);
    } catch (err) {
      setError(err.message || "Failed to load call details");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadCall();
  }, [loadCall]);

  if (loading) {
    return (
      <main className="container">
        <Skeleton width="220px" height={14} />
        <Skeleton width="320px" height={28} style={{ marginTop: 10 }} />
        <div className="detail-grid" style={{ marginTop: 24 }}>
          <div className="card">
            <Skeleton width="40%" height={14} />
            <Skeleton width="100%" height={120} style={{ marginTop: 14 }} />
          </div>
          <div className="card">
            <Skeleton width="55%" height={14} />
            <Skeleton width="100%" height={90} style={{ marginTop: 14 }} />
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="container">
        <div className="card">
          <Alert tone="danger">{error}</Alert>
          <Button variant="secondary" onClick={loadCall}>
            Retry
          </Button>
        </div>
      </main>
    );
  }

  if (!call) {
    return (
      <main className="container">
        <EmptyState
          icon={<IconInbox size={20} />}
          title="Call not found"
          description="This call may have been removed."
          action={
            <Link href="/calls" className="btn btn-secondary btn-sm">
              Back to calls
            </Link>
          }
        />
      </main>
    );
  }

  const title = call.contact_name || call.phone_number;
  const summary = call.summary;

  return (
    <main className="container">
      <Link href="/calls" className="back-link">
        <IconArrowLeft size={14} />
        All calls
      </Link>

      <div className="page-header">
        <div>
          <h1>
            {title} <Badge value={call.status} />
          </h1>
          <p className="page-sub num">
            {call.phone_number} · {formatDate(call.created_at)}
            {call.contact_name ? "" : " · No linked contact"}
          </p>
        </div>
        {call.status === "in_progress" ? (
          <div className="page-header-actions">
            <Link href={`/live-call/${id}`} className="btn">
              Open live session
            </Link>
          </div>
        ) : null}
      </div>

      <div className="detail-grid">
        {/* Left: transcript */}
        <div className="detail-col">
          <Card title="Transcript" sub={`${call.turns?.length || 0} turns recorded`}>
            {!call.turns || call.turns.length === 0 ? (
              <p className="card-sub" style={{ marginTop: 8 }}>
                No turns recorded — the call ended before the conversation started.
              </p>
            ) : (
              <div className="transcript">
                {call.turns.map((t) => (
                  <div key={t.turn_index} className={`bubble bubble-${t.speaker}`}>
                    <div className="bubble-meta">
                      <span className="bubble-speaker">{t.speaker}</span>
                      <span className="num">{formatTime(t.created_at)}</span>
                      {t.confidence != null ? (
                        <span className="num">{(t.confidence * 100).toFixed(0)}% conf</span>
                      ) : null}
                    </div>
                    {t.message}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right: intelligence cards */}
        <div className="detail-col">
          <Card title="AI summary">
            {summary ? (
              <>
                <p className="summary-text">{summary.summary || "—"}</p>
                {summary.customer_intent ? (
                  <div className="summary-section">
                    <p className="summary-section-title">Customer intent</p>
                    <p style={{ fontSize: 14 }}>{summary.customer_intent}</p>
                  </div>
                ) : null}
                {Array.isArray(summary.important_points) && summary.important_points.length > 0 ? (
                  <div className="summary-section">
                    <p className="summary-section-title">Important points</p>
                    <ul className="tidy-list">
                      {summary.important_points.map((point, i) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {Array.isArray(summary.followup_actions) && summary.followup_actions.length > 0 ? (
                  <div className="summary-section">
                    <p className="summary-section-title">Follow-up actions</p>
                    <ul className="tidy-list">
                      {summary.followup_actions.map((action, i) => (
                        <li key={i}>{action}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="card-sub" style={{ marginTop: 6 }}>
                No summary yet — it is written automatically when the call ends.
              </p>
            )}
          </Card>

          <Card title="Requirements" sub="What the agent captured during the call.">
            <div className="kv-list">
              {SLOT_KEYS.map(([key, label]) => (
                <KeyValue key={key} label={label} value={call.extracted_data?.[key]} />
              ))}
            </div>
          </Card>

          <Card title="Outcome">
            <div className="outcome-row">
              {call.outcome ? <Badge value={call.outcome} /> : <Badge value="unknown" tone="neutral">No outcome</Badge>}
              <Badge value={call.lead_status} />
              {call.followup_required ? <Badge value="followup">Follow-up needed</Badge> : <Badge value="neutral" tone="neutral">No follow-up</Badge>}
            </div>
          </Card>

          <Card title="Call info">
            <div className="kv-list">
              <KeyValue label="Duration" value={formatDuration(call.duration_seconds)} empty="—" />
              <KeyValue label="Direction" value={call.direction} />
              <KeyValue label="Started" value={call.start_time ? formatDate(call.start_time) : ""} empty="Not started" />
              <KeyValue label="Ended" value={call.end_time ? formatDate(call.end_time) : ""} empty="Not ended" />
            </div>
          </Card>

          <details className="events">
            <summary>
              Events log
              <span className="cell-muted num" style={{ fontWeight: 400 }}>
                {call.events?.length || 0}
              </span>
            </summary>
            <div className="events-body">
              {!call.events || call.events.length === 0 ? (
                <p className="card-sub" style={{ padding: "12px 14px", marginBottom: 0 }}>
                  No events logged for this call.
                </p>
              ) : (
                <div className="table-wrap" style={{ border: 0, borderRadius: 0 }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Event</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {call.events.map((ev, i) => (
                        <tr key={i}>
                          <td className="num cell-muted" style={{ whiteSpace: "nowrap" }}>
                            {formatDate(ev.created_at)}
                          </td>
                          <td>
                            <code>{ev.event_type}</code>
                          </td>
                          <td className="cell-muted" title={ev.detail ? JSON.stringify(ev.detail) : ""}>
                            {ev.detail ? JSON.stringify(ev.detail) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </details>
        </div>
      </div>
    </main>
  );
}

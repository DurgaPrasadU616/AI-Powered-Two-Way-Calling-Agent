"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

function formatDuration(sec) {
  if (sec == null || isNaN(sec)) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function CallsPage() {
  const [calls, setCalls] = useState([]);
  const [meta, setMeta] = useState({ page: 1, total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [customer, setCustomer] = useState("");
  const [status, setStatus] = useState("");
  const [leadStatus, setLeadStatus] = useState("");
  const [outcome, setOutcome] = useState("");
  const [followup, setFollowup] = useState("");
  const [page, setPage] = useState(1);

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.append("date_from", dateFrom);
      if (dateTo) params.append("date_to", dateTo);
      if (customer.trim()) params.append("customer", customer.trim());
      if (status) params.append("status", status);
      if (leadStatus) params.append("lead_status", leadStatus);
      if (outcome) params.append("outcome", outcome);
      if (followup !== "") params.append("followup_required", followup);
      params.append("page", String(page));
      params.append("page_size", "15");

      const res = await apiFetch(`/calls?${params.toString()}`);
      if (!res.ok) throw new Error(`Failed to load calls (${res.status})`);
      const data = await res.json();
      setCalls(data.items || []);
      setMeta(data.meta || { page: 1, total: 0, pages: 1 });
    } catch (err) {
      setError(err.message || "Failed to load calls");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, customer, status, leadStatus, outcome, followup, page]);

  useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  function handleReset() {
    setDateFrom("");
    setDateTo("");
    setCustomer("");
    setStatus("");
    setLeadStatus("");
    setOutcome("");
    setFollowup("");
    setPage(1);
  }

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h1>Call History & Transcripts</h1>
          <p className="sub">Outbound sales qualification calls with full intelligence logs.</p>
        </div>
        <Link href="/contacts" className="btn">+ Start New Call</Link>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <strong style={{ fontSize: 13, color: "var(--muted)" }}>Filter Calls</strong>
          <button
            onClick={handleReset}
            className="secondary"
            style={{ marginTop: 0, padding: "4px 10px", fontSize: 12 }}
          >
            Reset Filters
          </button>
        </div>

        <div className="filter-grid">
          <div>
            <label>Customer Name / Contact ID</label>
            <input
              placeholder="Search customer…"
              value={customer}
              onChange={(e) => { setCustomer(e.target.value); setPage(1); }}
            />
          </div>
          <div>
            <label>Status</label>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="disconnected">Disconnected</option>
              <option value="failed">Failed</option>
              <option value="no_answer">No Answer</option>
            </select>
          </div>
          <div>
            <label>Lead Status</label>
            <select value={leadStatus} onChange={(e) => { setLeadStatus(e.target.value); setPage(1); }}>
              <option value="">All Lead Statuses</option>
              <option value="hot">Hot</option>
              <option value="warm">Warm</option>
              <option value="cold">Cold</option>
              <option value="interested">Interested</option>
              <option value="not_interested">Not Interested</option>
            </select>
          </div>
          <div>
            <label>Outcome</label>
            <select value={outcome} onChange={(e) => { setOutcome(e.target.value); setPage(1); }}>
              <option value="">All Outcomes</option>
              <option value="interested">Interested</option>
              <option value="not_interested">Not Interested</option>
              <option value="callback_requested">Callback Requested</option>
              <option value="no_response">No Response</option>
              <option value="failed">Failed</option>
              <option value="incomplete">Incomplete</option>
            </select>
          </div>
          <div>
            <label>Follow-up</label>
            <select value={followup} onChange={(e) => { setFollowup(e.target.value); setPage(1); }}>
              <option value="">All</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div>
            <label>Date From</label>
            <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} />
          </div>
          <div>
            <label>Date To</label>
            <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} />
          </div>
        </div>
      </div>

      {error ? <div className="error" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="card">
        {loading ? (
          <p className="sub">Loading call records…</p>
        ) : calls.length === 0 ? (
          <p className="sub">No calls found matching the selected filters.</p>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Phone</th>
                    <th>Date</th>
                    <th>Duration (mm:ss)</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Lead Status</th>
                    <th>Follow-up</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => (
                    <tr key={call.id}>
                      <td><strong>{call.phone_number}</strong></td>
                      <td>{new Date(call.created_at).toLocaleDateString()}</td>
                      <td>{formatDuration(call.duration_seconds)}</td>
                      <td><span className={`badge ${call.status}`}>{call.status}</span></td>
                      <td>{call.outcome ? <span className={`badge ${call.outcome}`}>{call.outcome}</span> : "—"}</td>
                      <td><span className={`badge ${call.lead_status}`}>{call.lead_status}</span></td>
                      <td>
                        {call.followup_required ? (
                          <span style={{ color: "var(--warning)", fontWeight: 600 }}>Yes</span>
                        ) : (
                          "No"
                        )}
                      </td>
                      <td>
                        <Link
                          href={`/calls/${call.id}`}
                          style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}
                        >
                          View Detail →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span>Showing Page {meta.page} of {meta.pages} ({meta.total} total calls)</span>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className="secondary"
                  style={{ marginTop: 0 }}
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  className="secondary"
                  style={{ marginTop: 0 }}
                  disabled={page >= meta.pages}
                  onClick={() => setPage((p) => Math.min(meta.pages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

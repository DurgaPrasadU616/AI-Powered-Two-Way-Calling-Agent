"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

function formatDuration(sec) {
  if (sec == null || isNaN(sec)) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchStats() {
      setLoading(true);
      setError("");
      try {
        const res = await apiFetch("/dashboard/stats");
        if (!res.ok) {
          throw new Error(`Failed to load stats (${res.status})`);
        }
        const data = await res.json();
        setStats(data);
      } catch (err) {
        setError(err.message || "Failed to load dashboard statistics");
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h1>Dashboard Overview</h1>
          <p className="sub">Real-time metrics and qualification performance for outbound RO calls.</p>
        </div>
        <Link href="/contacts" className="btn">+ Start Call</Link>
      </div>

      {loading && (
        <div className="card">
          <p className="sub">Loading performance metrics…</p>
        </div>
      )}

      {error && !loading && (
        <div className="card">
          <div className="error">{error}</div>
        </div>
      )}

      {!loading && !error && !stats && (
        <div className="card">
          <p className="sub">No statistics available.</p>
        </div>
      )}

      {!loading && !error && stats && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Total Calls</div>
              <div className="stat-value">{stats.total_calls}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Completed</div>
              <div className="stat-value" style={{ color: "var(--accent-2)" }}>{stats.completed_calls}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Failed / No Answer</div>
              <div className="stat-value" style={{ color: "var(--danger)" }}>{stats.failed_calls}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Interested Leads</div>
              <div className="stat-value" style={{ color: "#4ade80" }}>{stats.interested_leads}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Follow-ups Required</div>
              <div className="stat-value" style={{ color: "var(--warning)" }}>{stats.followups_required}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg Duration (mm:ss)</div>
              <div className="stat-value">{formatDuration(stats.avg_duration_seconds)}</div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <h2>Quick Actions</h2>
            <div style={{ display: "flex", gap: "12px", marginTop: "12px", flexWrap: "wrap" }}>
              <Link href="/calls" className="btn secondary">View Call History & Transcripts</Link>
              <Link href="/contacts" className="btn secondary">View Leads & Contacts</Link>
            </div>
          </div>
        </>
      )}
    </main>
  );
}

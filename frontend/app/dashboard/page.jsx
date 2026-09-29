"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";
import { formatDuration, formatDate } from "../../lib/format";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import { SkeletonCards, Skeleton } from "../../components/ui/Skeleton";
import { IconArrowRight, IconPhone } from "../../components/ui/Icons";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsRes, callsRes] = await Promise.all([
        apiFetch("/dashboard/stats"),
        apiFetch("/calls?page=1&page_size=5"),
      ]);
      if (!statsRes.ok) throw new Error(`Could not load stats (${statsRes.status})`);
      if (!callsRes.ok) throw new Error(`Could not load recent calls (${callsRes.status})`);
      const statsData = await statsRes.json();
      const callsData = await callsRes.json();
      setStats(statsData);
      setRecent(callsData.items || []);
    } catch (err) {
      setError(err.message || "Failed to load the dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const STAT_DEFS = stats
    ? [
        { label: "Total calls", value: stats.total_calls, hint: "Everything you have dialled" },
        { label: "Completed", value: stats.completed_calls, hint: "Finished normally" },
        { label: "Failed / no answer", value: stats.failed_calls, hint: "Worth retrying" },
        { label: "Interested leads", value: stats.interested_leads, hint: "Outcome: interested" },
        { label: "Follow-ups", value: stats.followups_required, hint: "Marked for a callback" },
        {
          label: "Avg duration",
          value: formatDuration(stats.avg_duration_seconds),
          hint: "Per call, mm:ss",
        },
      ]
    : [];

  return (
    <main className="container">
      <PageHeader
        title="Overview"
        subtitle="Qualification performance for your outbound calls."
        action={
          <Link href="/contacts" className="btn">
            <IconPhone size={15} />
            Start a call
          </Link>
        }
      />

      {loading ? <SkeletonCards count={6} /> : null}

      {!loading && error ? (
        <div className="card">
          <Alert tone="danger">{error}</Alert>
          <Button variant="secondary" onClick={load}>
            Retry
          </Button>
        </div>
      ) : null}

      {!loading && !error && stats ? (
        <>
          <div className="stats-grid">
            {STAT_DEFS.map((stat) => (
              <StatCard key={stat.label} label={stat.label} value={stat.value} hint={stat.hint} />
            ))}
          </div>

          <Card
            title="Recent calls"
            actions={
              <Link href="/calls" className="link-more">
                View all
              </Link>
            }
          >
            {recent === null || recent.length === 0 ? (
              <EmptyState
                icon={<IconPhone size={20} />}
                title="No calls yet"
                description="Queue your first outbound call from the contacts page."
                action={
                  <Link href="/contacts" className="btn btn-secondary btn-sm">
                    Go to contacts
                  </Link>
                }
              />
            ) : (
              <div className="list-rows">
                {recent.map((call) => (
                  <Link key={call.id} href={`/calls/${call.id}`} className="list-row">
                    <span className="cell-strong num">{call.phone_number}</span>
                    <span className="row-meta">{formatDate(call.created_at)}</span>
                    <span className="row-end">
                      <span className="row-meta num">{formatDuration(call.duration_seconds)}</span>
                      <Badge value={call.status} />
                      <IconArrowRight size={14} aria-hidden="true" />
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </>
      ) : null}

      {!loading && !error && !stats ? (
        <div className="card">
          <p className="card-sub">No statistics available yet.</p>
          <Skeleton width="50%" height={14} />
        </div>
      ) : null}
    </main>
  );
}

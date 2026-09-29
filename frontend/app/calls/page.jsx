"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../lib/api";
import { formatDuration, formatDate } from "../../lib/format";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Table from "../../components/ui/Table";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Alert from "../../components/ui/Alert";
import EmptyState from "../../components/ui/EmptyState";
import Pagination from "../../components/ui/Pagination";
import { Input, Select } from "../../components/ui/Field";
import { SkeletonTable } from "../../components/ui/Skeleton";
import { IconSearch, IconRefresh, IconChevronRight, IconPhone } from "../../components/ui/Icons";

const EMPTY_FILTERS = {
  customer: "",
  status: "",
  leadStatus: "",
  outcome: "",
  followup: "",
  dateFrom: "",
  dateTo: "",
};

const PAGE_SIZE = 15;

export default function CallsPage() {
  const router = useRouter();
  const [calls, setCalls] = useState([]);
  const [meta, setMeta] = useState({ page: 1, page_size: PAGE_SIZE, total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (applied.dateFrom) params.append("date_from", applied.dateFrom);
      if (applied.dateTo) params.append("date_to", applied.dateTo);
      if (applied.customer.trim()) params.append("customer", applied.customer.trim());
      if (applied.status) params.append("status", applied.status);
      if (applied.leadStatus) params.append("lead_status", applied.leadStatus);
      if (applied.outcome) params.append("outcome", applied.outcome);
      if (applied.followup !== "") params.append("followup_required", applied.followup);
      params.append("page", String(page));
      params.append("page_size", String(PAGE_SIZE));

      const res = await apiFetch(`/calls?${params.toString()}`);
      if (!res.ok) throw new Error(`Could not load calls (${res.status})`);
      const data = await res.json();
      setCalls(data.items || []);
      setMeta(data.meta || { page: 1, page_size: PAGE_SIZE, total: 0, pages: 1 });
    } catch (err) {
      setError(err.message || "Failed to load calls");
    } finally {
      setLoading(false);
    }
  }, [applied, page]);

  useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  function setDraftField(key, value) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function handleApply(e) {
    if (e) e.preventDefault();
    setPage(1);
    setApplied({ ...draft });
  }

  function handleReset() {
    setDraft(EMPTY_FILTERS);
    setPage(1);
    setApplied(EMPTY_FILTERS);
  }

  function openCall(id) {
    router.push(`/calls/${id}`);
  }

  const hasFilters = Object.values(draft).some((v) => v !== "");

  return (
    <main className="container">
      <PageHeader
        title="Calls"
        subtitle="Every outbound call, its transcript and its outcome."
        action={
          <button type="button" className="btn" onClick={() => router.push("/contacts")}>
            <IconPhone size={15} />
            Start a call
          </button>
        }
      />

      <Card>
        <form onSubmit={handleApply}>
          <div className="filter-grid">
            <Input
              label="Customer"
              placeholder="Name or contact ID"
              value={draft.customer}
              onChange={(e) => setDraftField("customer", e.target.value)}
            />
            <Select
              label="Status"
              value={draft.status}
              onChange={(e) => setDraftField("status", e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="disconnected">Disconnected</option>
              <option value="failed">Failed</option>
              <option value="no_answer">No answer</option>
            </Select>
            <Select
              label="Lead status"
              value={draft.leadStatus}
              onChange={(e) => setDraftField("leadStatus", e.target.value)}
            >
              <option value="">All lead statuses</option>
              <option value="hot">Hot</option>
              <option value="warm">Warm</option>
              <option value="cold">Cold</option>
              <option value="interested">Interested</option>
              <option value="not_interested">Not interested</option>
              <option value="unknown">Unknown</option>
            </Select>
            <Select
              label="Outcome"
              value={draft.outcome}
              onChange={(e) => setDraftField("outcome", e.target.value)}
            >
              <option value="">All outcomes</option>
              <option value="interested">Interested</option>
              <option value="not_interested">Not interested</option>
              <option value="callback_requested">Callback requested</option>
              <option value="no_response">No response</option>
              <option value="failed">Failed</option>
              <option value="incomplete">Incomplete</option>
            </Select>
            <Select
              label="Follow-up"
              value={draft.followup}
              onChange={(e) => setDraftField("followup", e.target.value)}
            >
              <option value="">Any</option>
              <option value="true">Required</option>
              <option value="false">Not required</option>
            </Select>
            <Input
              label="Date from"
              type="date"
              value={draft.dateFrom}
              onChange={(e) => setDraftField("dateFrom", e.target.value)}
            />
            <Input
              label="Date to"
              type="date"
              value={draft.dateTo}
              onChange={(e) => setDraftField("dateTo", e.target.value)}
            />
          </div>

          <div className="filter-actions">
            <Button type="submit" size="sm" icon={<IconSearch size={14} />}>
              Apply
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<IconRefresh size={14} />}
              onClick={handleReset}
              disabled={!hasFilters && page === 1}
            >
              Reset
            </Button>
          </div>
        </form>
      </Card>

      {error ? (
        <div className="card">
          <Alert tone="danger">{error}</Alert>
          <Button variant="secondary" onClick={fetchCalls}>
            Retry
          </Button>
        </div>
      ) : null}

      {!error && loading ? (
        <SkeletonTable rows={6} cols={7} />
      ) : !error && calls.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<IconSearch size={20} />}
            title="No calls match"
            description="Try widening the filters, or reset them to see every call."
            action={
              <Button variant="secondary" onClick={handleReset}>
                Reset filters
              </Button>
            }
          />
        </div>
      ) : !error ? (
        <div className="card">
          <Table>
            <thead>
              <tr>
                <th>Phone</th>
                <th>Date</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Lead</th>
                <th>Follow-up</th>
                <th aria-label="Open" />
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr
                  key={call.id}
                  className="row-clickable"
                  tabIndex={0}
                  role="link"
                  aria-label={`Open call ${call.phone_number}`}
                  onClick={() => openCall(call.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openCall(call.id);
                    }
                  }}
                >
                  <td className="cell-strong num">{call.phone_number}</td>
                  <td className="cell-muted num">{formatDate(call.created_at)}</td>
                  <td className="num">{formatDuration(call.duration_seconds)}</td>
                  <td>
                    <Badge value={call.status} />
                  </td>
                  <td>{call.outcome ? <Badge value={call.outcome} /> : <span className="cell-muted">—</span>}</td>
                  <td>
                    <Badge value={call.lead_status} />
                  </td>
                  <td>
                    {call.followup_required ? (
                      <Badge value="followup">Yes</Badge>
                    ) : (
                      <span className="cell-muted">No</span>
                    )}
                  </td>
                  <td style={{ textAlign: "right", color: "var(--muted)" }}>
                    <IconChevronRight size={14} aria-hidden="true" />
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>

          <Pagination
            page={meta.page}
            pages={meta.pages}
            total={meta.total}
            pageSize={meta.page_size || PAGE_SIZE}
            busy={loading}
            onPage={setPage}
          />
        </div>
      ) : null}
    </main>
  );
}

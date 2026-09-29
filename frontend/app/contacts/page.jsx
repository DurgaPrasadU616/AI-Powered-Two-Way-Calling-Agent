"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../lib/api";
import { truncate } from "../../lib/format";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Table from "../../components/ui/Table";
import Button from "../../components/ui/Button";
import Alert from "../../components/ui/Alert";
import EmptyState from "../../components/ui/EmptyState";
import { Input } from "../../components/ui/Field";
import { SkeletonTable } from "../../components/ui/Skeleton";
import { IconPlus, IconPhone, IconTrash, IconInbox } from "../../components/ui/Icons";

const E164 = /^\+[1-9]\d{7,14}$/;

export default function ContactsPage() {
  const router = useRouter();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  // Add contact form state
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("+91");
  const [company, setCompany] = useState("");
  const [purpose, setPurpose] = useState("Sales outreach");
  const [product, setProduct] = useState("Commercial RO 1000 LPH");
  const [createLoading, setCreateLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/contacts?page_size=100");
      if (!res.ok) throw new Error(`Could not load contacts (${res.status})`);
      const data = await res.json();
      // GET /contacts returns a bare array
      setContacts(Array.isArray(data) ? data : data.items || []);
    } catch (err) {
      setError(err.message || "Failed to load contacts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

  function validate() {
    const errs = {};
    if (!name.trim()) errs.name = "Name is required.";
    if (!E164.test(phone.trim())) errs.phone = "Use E.164 format, e.g. +919876543210.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleAddContact(e) {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;

    setCreateLoading(true);
    try {
      const res = await apiFetch("/contacts", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          phone_e164: phone.trim(),
          company: company.trim() || null,
          purpose: purpose.trim() || null,
          product: product.trim() || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        let msg = `Could not save the contact (${res.status})`;
        if (data.detail) {
          if (Array.isArray(data.detail)) {
            msg = data.detail.map((err) => `${err.loc?.join(".") || "field"}: ${err.msg}`).join(" · ");
          } else {
            msg = String(data.detail);
          }
        }
        throw new Error(msg);
      }

      setShowAdd(false);
      setName("");
      setPhone("+91");
      setCompany("");
      setFieldErrors({});
      await fetchContacts();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleStartCall(contactId) {
    setCallingId(contactId);
    setError("");
    try {
      const res = await apiFetch("/calls", {
        method: "POST",
        body: JSON.stringify({ contact_id: contactId }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Could not queue the call (${res.status})`);
      }
      const call = await res.json();
      router.push(`/live-call/${call.id}`);
    } catch (err) {
      setError(err.message);
      setCallingId(null);
    }
  }

  async function handleDelete(contact) {
    const confirmed = window.confirm(`Delete ${contact.name}? This cannot be undone.`);
    if (!confirmed) return;
    setDeletingId(contact.id);
    setError("");
    try {
      const res = await apiFetch(`/contacts/${contact.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        throw new Error(`Could not delete the contact (${res.status})`);
      }
      await fetchContacts();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="container">
      <PageHeader
        title="Contacts"
        subtitle="Leads you call, with the details the agent greets them with."
        action={
          <Button onClick={() => setShowAdd((v) => !v)} icon={showAdd ? undefined : <IconPlus size={15} />}>
            {showAdd ? "Close" : "Add contact"}
          </Button>
        }
      />

      {showAdd ? (
        <Card title="Add contact" sub="The agent uses these details to open the conversation.">
          <form onSubmit={handleAddContact} noValidate>
            {formError ? <Alert tone="danger">{formError}</Alert> : null}

            <div className="form-grid">
              <Input
                label="Name *"
                id="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Rahul Kumar"
                error={fieldErrors.name}
              />
              <Input
                label="Phone (E.164) *"
                id="phone"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+919876543210"
                error={fieldErrors.phone}
                hint="Country code followed by the number."
              />
              <Input
                label="Company"
                id="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g. Orchid Hotel"
              />
              <Input
                label="Purpose"
                id="purpose"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="e.g. RO plant qualification"
              />
              <Input
                label="Product"
                id="product"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g. Commercial RO 1000 LPH"
              />
            </div>

            <div className="form-actions">
              <Button type="submit" loading={createLoading}>
                {createLoading ? "Saving…" : "Save contact"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowAdd(false);
                  setFormError("");
                  setFieldErrors({});
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      {error ? <Alert tone="danger">{error}</Alert> : null}

      {loading ? (
        <SkeletonTable rows={5} cols={6} />
      ) : contacts.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<IconInbox size={20} />}
            title="No contacts yet"
            description="Add your first lead and the agent will call them with a tailored greeting."
            action={
              <Button
                icon={<IconPlus size={15} />}
                onClick={() => {
                  setShowAdd(true);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                Add contact
              </Button>
            }
          />
        </div>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Company</th>
              <th>Purpose</th>
              <th>Product</th>
              <th style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id}>
                <td className="cell-strong" title={c.name}>
                  {truncate(c.name, 28)}
                </td>
                <td className="num">{c.phone_e164}</td>
                <td className="cell-muted" title={c.company || ""}>
                  {c.company ? truncate(c.company, 24) : "—"}
                </td>
                <td className="cell-muted" title={c.purpose || ""}>
                  {c.purpose ? truncate(c.purpose, 26) : "—"}
                </td>
                <td className="cell-muted" title={c.product || ""}>
                  {c.product ? truncate(c.product, 24) : "—"}
                </td>
                <td>
                  <div className="cell-actions">
                    <Button
                      size="sm"
                      icon={callingId === c.id ? undefined : <IconPhone size={14} />}
                      loading={callingId === c.id}
                      onClick={() => handleStartCall(c.id)}
                    >
                      {callingId === c.id ? "Starting…" : "Start call"}
                    </Button>
                    <button
                      type="button"
                      className="btn btn-icon"
                      onClick={() => handleDelete(c)}
                      disabled={deletingId === c.id}
                      aria-label={`Delete ${c.name}`}
                      title={`Delete ${c.name}`}
                    >
                      {deletingId === c.id ? <span className="spinner" aria-hidden="true" /> : <IconTrash size={14} />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </main>
  );
}

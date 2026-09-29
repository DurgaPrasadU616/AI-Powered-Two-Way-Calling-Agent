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
import { IconPlus, IconPhone, IconTrash, IconInbox, IconEdit, IconSearch } from "../../components/ui/Icons";

const E164 = /^\+[1-9]\d{7,14}$/;

export default function ContactsPage() {
  const router = useRouter();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [search, setSearch] = useState("");

  // Add contact form state
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("+91");
  const [company, setCompany] = useState("");
  const [purpose, setPurpose] = useState("Sales outreach");
  const [product, setProduct] = useState("Commercial RO 1000 LPH");
  const [createLoading, setCreateLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  // Edit contact form state
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editPurpose, setEditPurpose] = useState("");
  const [editProduct, setEditProduct] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState("");

  const fetchContacts = useCallback(async (q = "") => {
    setLoading(true);
    setError("");
    try {
      const url = q.trim()
        ? `/contacts?q=${encodeURIComponent(q.trim())}&page_size=100`
        : "/contacts?page_size=100";
      const res = await apiFetch(url);
      if (!res.ok) throw new Error(`Could not load contacts (${res.status})`);
      const data = await res.json();
      setContacts(Array.isArray(data) ? data : data.items || []);
    } catch (err) {
      setError(err.message || "Failed to load contacts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContacts(search);
  }, [fetchContacts, search]);

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
      await fetchContacts(search);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setCreateLoading(false);
    }
  }

  function handleStartEdit(c) {
    setEditingId(c.id);
    setEditName(c.name || "");
    setEditPhone(c.phone_e164 || "");
    setEditCompany(c.company || "");
    setEditPurpose(c.purpose || "");
    setEditProduct(c.product || "");
    setEditError("");
    setShowAdd(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSaveEdit(e) {
    e.preventDefault();
    if (!editName.trim()) {
      setEditError("Name is required.");
      return;
    }
    if (!E164.test(editPhone.trim())) {
      setEditError("Phone must be in E.164 format (e.g. +919876543210).");
      return;
    }
    setEditLoading(true);
    setEditError("");
    try {
      const res = await apiFetch(`/contacts/${editingId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editName.trim(),
          phone_e164: editPhone.trim(),
          company: editCompany.trim() || null,
          purpose: editPurpose.trim() || null,
          product: editProduct.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Could not update contact (${res.status})`);
      }
      setEditingId(null);
      await fetchContacts(search);
    } catch (err) {
      setEditError(err.message);
    } finally {
      setEditLoading(false);
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
    const confirmed = window.confirm(`Delete ${contact.name}? Call history will be preserved.`);
    if (!confirmed) return;
    setDeletingId(contact.id);
    setError("");
    try {
      const res = await apiFetch(`/contacts/${contact.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        throw new Error(`Could not delete the contact (${res.status})`);
      }
      await fetchContacts(search);
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
          <Button
            onClick={() => {
              setEditingId(null);
              setShowAdd((v) => !v);
            }}
            icon={showAdd ? undefined : <IconPlus size={15} />}
          >
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

      {editingId ? (
        <Card title="Edit contact" sub="Update contact details used during agent calls.">
          <form onSubmit={handleSaveEdit} noValidate>
            {editError ? <Alert tone="danger">{editError}</Alert> : null}

            <div className="form-grid">
              <Input
                label="Name *"
                id="edit_name"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
              <Input
                label="Phone (E.164) *"
                id="edit_phone"
                required
                value={editPhone}
                onChange={(e) => setEditPhone(e.target.value)}
                hint="Country code followed by number (e.g. +919876543210)"
              />
              <Input
                label="Company"
                id="edit_company"
                value={editCompany}
                onChange={(e) => setEditCompany(e.target.value)}
              />
              <Input
                label="Purpose"
                id="edit_purpose"
                value={editPurpose}
                onChange={(e) => setEditPurpose(e.target.value)}
              />
              <Input
                label="Product"
                id="edit_product"
                value={editProduct}
                onChange={(e) => setEditProduct(e.target.value)}
              />
            </div>

            <div className="form-actions">
              <Button type="submit" loading={editLoading}>
                {editLoading ? "Updating…" : "Update contact"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setEditingId(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      {/* Search Input Bar */}
      <div style={{ marginBottom: 16 }}>
        <Input
          placeholder="Search contacts by name or company..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search contacts"
        />
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      {loading ? (
        <SkeletonTable rows={5} cols={6} />
      ) : contacts.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<IconInbox size={20} />}
            title={search ? "No matching contacts" : "No contacts yet"}
            description={
              search
                ? `No contact names or companies match "${search}".`
                : "Add your first lead and the agent will call them with a tailored greeting."
            }
            action={
              search ? (
                <Button variant="secondary" onClick={() => setSearch("")}>
                  Clear search
                </Button>
              ) : (
                <Button
                  icon={<IconPlus size={15} />}
                  onClick={() => {
                    setShowAdd(true);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  Add contact
                </Button>
              )
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
                      onClick={() => handleStartEdit(c)}
                      aria-label={`Edit ${c.name}`}
                      title={`Edit ${c.name}`}
                    >
                      <IconEdit size={14} />
                    </button>
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

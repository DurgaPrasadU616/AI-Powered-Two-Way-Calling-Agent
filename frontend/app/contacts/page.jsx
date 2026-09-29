"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../lib/api";

export default function ContactsPage() {
  const router = useRouter();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState(null);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  // Add contact form state
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("+91");
  const [company, setCompany] = useState("");
  const [purpose, setPurpose] = useState("Sales Outreach");
  const [product, setProduct] = useState("Commercial RO 1000 LPH");
  const [createLoading, setCreateLoading] = useState(false);
  const [formError, setFormError] = useState("");

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/contacts?page_size=100");
      if (!res.ok) throw new Error(`Failed to load contacts (${res.status})`);
      const data = await res.json();
      setContacts(data.items || []);
    } catch (err) {
      setError(err.message || "Failed to load contacts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

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
        throw new Error(errData.detail || `Failed to queue call (${res.status})`);
      }
      const call = await res.json();
      router.push(`/live-call/${call.id}`);
    } catch (err) {
      setError(err.message);
      setCallingId(null);
    }
  }

  async function handleAddContact(e) {
    e.preventDefault();
    setCreateLoading(true);
    setFormError("");

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
        let msg = `Creation failed (${res.status})`;
        if (data.detail) {
          if (Array.isArray(data.detail)) {
            msg = data.detail.map((err) => `${err.loc?.join(".") || "field"}: ${err.msg}`).join(" | ");
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
      await fetchContacts();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setCreateLoading(false);
    }
  }

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h1>Leads & Contacts</h1>
          <p className="sub">Pre-qualified business leads for outbound commercial water treatment calls.</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? "Cancel" : "+ Add Contact"}
        </button>
      </div>

      {showAdd && (
        <form className="card" onSubmit={handleAddContact} style={{ marginBottom: 20 }}>
          <h2>Add Contact</h2>
          <p className="sub">Enter business lead details. Phone number must be strict E.164 format (e.g. +919876543210).</p>

          <label htmlFor="name">Full Name *</label>
          <input
            id="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Rahul Kumar"
          />

          <label htmlFor="phone">Phone (E.164 format) *</label>
          <input
            id="phone"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+919876543210"
          />

          <label htmlFor="company">Company / Organization</label>
          <input
            id="company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Orchid Hotel"
          />

          <label htmlFor="purpose">Purpose</label>
          <input
            id="purpose"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="e.g. RO water plant qualification"
          />

          <label htmlFor="product">Product</label>
          <input
            id="product"
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="e.g. Commercial RO 1000 LPH"
          />

          {formError ? <div className="error">{formError}</div> : null}

          <button type="submit" disabled={createLoading} style={{ marginTop: 16 }}>
            {createLoading ? "Saving…" : "Save Contact"}
          </button>
        </form>
      )}

      {error ? <div className="error" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="card">
        {loading ? (
          <p className="sub">Loading contacts database…</p>
        ) : contacts.length === 0 ? (
          <p className="sub">No contacts found. Click "+ Add Contact" above to create one.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone (E.164)</th>
                  <th>Company</th>
                  <th>Purpose</th>
                  <th>Product</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((c) => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong></td>
                    <td><code>{c.phone_e164}</code></td>
                    <td>{c.company || "—"}</td>
                    <td>{c.purpose || "—"}</td>
                    <td>{c.product || "—"}</td>
                    <td>
                      <button
                        style={{ marginTop: 0, padding: "6px 12px", fontSize: 13 }}
                        disabled={callingId === c.id}
                        onClick={() => handleStartCall(c.id)}
                      >
                        {callingId === c.id ? "Connecting…" : "📞 Start Call"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@sephawk.com");
  const [password, setPassword] = useState("Admin@123");
  const [phone, setPhone] = useState("+919876543210");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function startCall(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const login = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!login.ok) {
        throw new Error(`Login failed (${login.status})`);
      }
      const { access_token } = await login.json();
      sessionStorage.setItem("token", access_token);

      const created = await fetch(`${API}/calls`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify({ phone_number: phone }),
      });
      if (!created.ok) {
        throw new Error(`Could not create call (${created.status})`);
      }
      const call = await created.json();
      router.push(`/live-call/${call.id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <h1>SERP Hawk — AI Calling Agent</h1>
      <p className="sub">
        Sign in, create an outbound call, then talk to the agent in your browser.
      </p>
      <form className="card" onSubmit={startCall}>
        <label htmlFor="email">Admin email</label>
        <input id="email" value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <label htmlFor="phone">Customer phone (E.164)</label>
        <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />

        <button type="submit" disabled={busy}>
          {busy ? "Starting…" : "Start live call"}
        </button>
        {error ? <div className="error">{error}</div> : null}
      </form>
    </main>
  );
}

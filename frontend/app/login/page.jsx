"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setToken } from "../../lib/api";
import Button from "../../components/ui/Button";
import { Input } from "../../components/ui/Field";
import Alert from "../../components/ui/Alert";
import { IconEye, IconEyeOff, IconPhone } from "../../components/ui/Icons";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@sephawk.com");
  const [password, setPassword] = useState("Admin@123");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        let msg = `Login failed (${res.status})`;
        try {
          const data = await res.json();
          if (data && data.detail) {
            msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
          }
        } catch {}
        throw new Error(msg);
      }

      const data = await res.json();
      setToken(data.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err.message || "Login failed");
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="auth-head">
          <span className="brand-mark" aria-hidden="true" style={{ display: "inline-flex" }}>
            <IconPhone size={16} />
          </span>
          <h1>Calling Agent</h1>
          <p className="auth-sub">Sign in to run and review outbound calls.</p>
        </div>

        <form className="card" onSubmit={handleLogin}>
          {error ? <Alert tone="danger">{error}</Alert> : null}

          <Input
            label="Email"
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@sephawk.com"
          />

          <div className="field">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <div className="input-group">
              <input
                id="password"
                className="input"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
              <button
                type="button"
                className="input-affix"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              </button>
            </div>
          </div>

          <Button type="submit" block loading={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </main>
  );
}

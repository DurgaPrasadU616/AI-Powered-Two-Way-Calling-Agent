"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getToken, clearToken } from "../lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const token = getToken();
    if (!token && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router]);

  if (!mounted || pathname === "/login") {
    return null;
  }

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  return (
    <header className="navbar">
      <div className="nav-container">
        <Link href="/dashboard" className="nav-brand">
          <span className="brand-dot" />
          <strong>SERP Hawk</strong> <span className="brand-tag">AI Calling Agent</span>
        </Link>
        <nav className="nav-links">
          <Link href="/dashboard" className={`nav-link ${pathname === "/dashboard" ? "active" : ""}`}>
            Dashboard
          </Link>
          <Link href="/contacts" className={`nav-link ${pathname === "/contacts" ? "active" : ""}`}>
            Contacts
          </Link>
          <Link href="/calls" className={`nav-link ${pathname.startsWith("/calls") ? "active" : ""}`}>
            Calls
          </Link>
          <button
            onClick={handleLogout}
            className="secondary"
            style={{ marginTop: 0, padding: "5px 10px", fontSize: 12 }}
          >
            Logout
          </button>
        </nav>
      </div>
    </header>
  );
}

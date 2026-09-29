"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getToken, clearToken } from "../lib/api";
import { IconPhone } from "./ui/Icons";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/contacts", label: "Contacts" },
  { href: "/calls", label: "Calls" },
];

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

  function isActive(href) {
    return href === "/calls" ? pathname.startsWith("/calls") : pathname === href;
  }

  return (
    <header className="navbar">
      <div className="nav-container">
        <Link href="/dashboard" className="nav-brand">
          <span className="brand-mark" aria-hidden="true">
            <IconPhone size={15} />
          </span>
          Calling Agent
        </Link>

        <nav className="nav-links" aria-label="Main">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link ${isActive(link.href) ? "active" : ""}`}
              aria-current={isActive(link.href) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <span className="nav-spacer" />

        <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}

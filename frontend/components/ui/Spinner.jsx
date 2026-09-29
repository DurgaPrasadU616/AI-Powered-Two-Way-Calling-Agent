"use client";

export function Spinner({ large = false, className = "" }) {
  return <span className={`spinner ${large ? "spinner-lg" : ""} ${className}`.trim()} aria-hidden="true" />;
}

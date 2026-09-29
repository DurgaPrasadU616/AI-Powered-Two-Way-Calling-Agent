"use client";

/**
 * Status pill. Tone follows the product rules:
 * success = completed / interested, warning = follow-up / callback,
 * red = failed / no answer, neutral = everything else.
 */
const SUCCESS = ["completed", "interested", "hot"];
const WARNING = ["queued", "callback_requested", "followup", "warm"];
const DANGER = ["failed", "no_answer", "disconnected"];
const ACCENT = ["in_progress"];

export function badgeTone(value) {
  const v = String(value || "").toLowerCase();
  if (SUCCESS.includes(v)) return "success";
  if (WARNING.includes(v)) return "warning";
  if (DANGER.includes(v)) return "danger";
  if (ACCENT.includes(v)) return "accent";
  return "neutral";
}

export function humanize(value) {
  if (value == null) return "—";
  return String(value).replace(/_/g, " ");
}

export default function Badge({ value, tone, children }) {
  const finalTone = tone || badgeTone(value);
  return <span className={`badge badge-${finalTone}`}>{children || humanize(value)}</span>;
}

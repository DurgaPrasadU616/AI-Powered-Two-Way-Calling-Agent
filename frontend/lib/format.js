/* Formatting helpers — shared across pages. */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function pad(n) {
  return String(n).padStart(2, "0");
}

/** Seconds → "mm:ss" (tabular friendly). */
export function formatDuration(sec) {
  if (sec == null || Number.isNaN(Number(sec))) return "00:00";
  const total = Math.max(0, Math.floor(Number(sec)));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${pad(m)}:${pad(s)}`;
}

/** ISO date → "29 Sep 2026, 14:05". */
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** ISO date → "14:05". */
export function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Shorten long text for table cells (pair with title= for the full value). */
export function truncate(text, max = 42) {
  const value = text == null ? "" : String(text);
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

"use client";

/** Inline alert. tone: danger | success | warning | info. */
export default function Alert({ tone = "danger", children, role, ...props }) {
  const alertRole = role || (tone === "danger" ? "alert" : "status");
  return (
    <div className={`alert alert-${tone}`} role={alertRole} {...props}>
      {children}
    </div>
  );
}

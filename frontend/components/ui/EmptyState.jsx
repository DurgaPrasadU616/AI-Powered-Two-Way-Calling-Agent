"use client";

export default function EmptyState({ icon = null, title, description, action = null }) {
  return (
    <div className="empty">
      {icon ? <div className="empty-icon">{icon}</div> : null}
      <p className="empty-title">{title}</p>
      {description ? <p className="empty-desc">{description}</p> : null}
      {action}
    </div>
  );
}

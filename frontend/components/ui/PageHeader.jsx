"use client";

export default function PageHeader({ title, subtitle, action = null }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p className="page-sub">{subtitle}</p> : null}
      </div>
      {action ? <div className="page-header-actions">{action}</div> : null}
    </div>
  );
}

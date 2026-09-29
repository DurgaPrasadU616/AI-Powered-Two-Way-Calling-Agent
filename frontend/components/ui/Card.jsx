"use client";

export default function Card({ title, sub, actions, children, className = "", ...props }) {
  return (
    <section className={`card ${className}`.trim()} {...props}>
      {title ? (
        <div className="card-head">
          <div>
            <h2 className="card-title">{title}</h2>
            {sub ? <p className="card-sub">{sub}</p> : null}
          </div>
          {actions ? <div className="page-header-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

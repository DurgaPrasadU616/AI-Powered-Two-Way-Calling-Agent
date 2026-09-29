"use client";

/** Standard table shell — pages supply thead/tbody. */
export default function Table({ children, className = "" }) {
  return (
    <div className={`table-wrap ${className}`.trim()}>
      <table className="table">{children}</table>
    </div>
  );
}

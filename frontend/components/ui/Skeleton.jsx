"use client";

export function Skeleton({ width = "100%", height = 16, radius = 6, className = "", style }) {
  return (
    <span
      className={`skeleton ${className}`.trim()}
      style={{ width, height, borderRadius: radius, ...style }}
      aria-hidden="true"
    />
  );
}

export default Skeleton;

/** Skeleton placeholder rows for a data table. */
export function SkeletonTable({ rows = 5, cols = 5 }) {
  return (
    <div className="table-wrap" aria-hidden="true">
      <table className="table">
        <thead>
          <tr>
            {Array.from({ length: cols }, (_, i) => (
              <th key={i}>
                <Skeleton width="70%" height={10} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }, (_, r) => (
            <tr key={r}>
              {Array.from({ length: cols }, (_, c) => (
                <td key={c}>
                  <Skeleton width={c === 0 ? "80%" : "55%"} height={12} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Skeleton placeholder stat cards. */
export function SkeletonCards({ count = 6 }) {
  return (
    <div className="stats-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div className="stat-card" key={i}>
          <Skeleton width="45%" height={11} />
          <Skeleton width="60%" height={28} style={{ marginTop: 8 }} />
          <Skeleton width="70%" height={10} style={{ marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}

"use client";

import Button from "./Button";

/** Prev/Next with a "showing X–Y of Z" range. */
export default function Pagination({ page, pages, total, pageSize, onPage, busy = false }) {
  const safePage = Math.max(1, page || 1);
  const safePages = Math.max(1, pages || 1);
  const from = total === 0 ? 0 : (safePage - 1) * (pageSize || 15) + 1;
  const to = Math.min(total || 0, safePage * (pageSize || 15));

  return (
    <div className="pagination">
      <span>
        Showing {from}–{to} of {total} calls
      </span>
      <div className="pagination-controls">
        <Button
          variant="secondary"
          size="sm"
          disabled={safePage <= 1 || busy}
          onClick={() => onPage(safePage - 1)}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={safePage >= safePages || busy}
          onClick={() => onPage(safePage + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

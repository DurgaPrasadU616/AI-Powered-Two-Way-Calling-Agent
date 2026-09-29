"use client";

import { useId } from "react";

/** Label + control + inline error, wired together for accessibility. */
export function Field({ label, error, hint, htmlFor, children }) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="field-hint">{hint}</p>
      ) : null}
    </div>
  );
}

export function Input({ label, error, hint, className = "", id, ...props }) {
  const autoId = useId();
  const inputId = id || autoId;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={inputId}>
      <input
        id={inputId}
        className={`input ${className}`.trim()}
        aria-invalid={error ? "true" : undefined}
        {...props}
      />
    </Field>
  );
}

export function Select({ label, error, hint, id, children, ...props }) {
  const autoId = useId();
  const selectId = id || autoId;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={selectId}>
      <select id={selectId} className="select" aria-invalid={error ? "true" : undefined} {...props}>
        {children}
      </select>
    </Field>
  );
}

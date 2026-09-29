"use client";

import { Spinner } from "./Spinner";

const VARIANTS = {
  primary: "btn",
  secondary: "btn btn-secondary",
  ghost: "btn btn-ghost",
  danger: "btn btn-danger",
};

export default function Button({
  variant = "primary",
  size,
  loading = false,
  block = false,
  icon = null,
  className = "",
  children,
  disabled,
  ...props
}) {
  const classes = [
    VARIANTS[variant] || VARIANTS.primary,
    size === "sm" ? "btn-sm" : "",
    block ? "btn-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={classes} disabled={disabled || loading} {...props}>
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}

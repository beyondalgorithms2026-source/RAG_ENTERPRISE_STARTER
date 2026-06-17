import { InputHTMLAttributes, ReactNode } from "react";

type ToggleProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label?: ReactNode;
  variant?: "checkbox" | "switch";
};

export function Toggle({ label, variant = "checkbox", className = "", ...props }: ToggleProps) {
  return (
    <label className={`ui-toggle ui-toggle-${variant} ${className}`.trim()}>
      <input type="checkbox" {...props} />
      {variant === "switch" ? <span className="ui-toggle-track" aria-hidden="true"><i /></span> : null}
      {label ? <span>{label}</span> : null}
    </label>
  );
}

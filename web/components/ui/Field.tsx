import { ReactNode } from "react";

type FieldProps = {
  label?: ReactNode;
  help?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Field({ label, help, error, children, className = "" }: FieldProps) {
  return (
    <label className={`ui-field ${className}`.trim()}>
      {label ? <span className="ui-field-label">{label}</span> : null}
      {children}
      {error ? <span className="ui-field-error">{error}</span> : help ? <span className="ui-field-help">{help}</span> : null}
    </label>
  );
}

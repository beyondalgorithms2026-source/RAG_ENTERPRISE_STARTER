import { HTMLAttributes } from "react";

export function FormActions({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`ui-form-actions ${className}`.trim()} {...props} />;
}

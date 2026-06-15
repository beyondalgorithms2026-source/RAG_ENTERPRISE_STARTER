import { forwardRef, InputHTMLAttributes } from "react";

export const NumberInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function NumberInput({ className = "", type = "number", ...props }, ref) {
    return <input ref={ref} type={type} className={`ui-control ${className}`.trim()} {...props} />;
  }
);

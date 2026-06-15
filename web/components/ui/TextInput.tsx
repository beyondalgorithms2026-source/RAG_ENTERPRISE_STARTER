import { forwardRef, InputHTMLAttributes } from "react";

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className = "", ...props }, ref) {
    return <input ref={ref} className={`ui-control ${className}`.trim()} {...props} />;
  }
);

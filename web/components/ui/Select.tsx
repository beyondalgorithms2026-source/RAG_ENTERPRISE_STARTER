import { forwardRef, SelectHTMLAttributes } from "react";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className = "", children, ...props }, ref) {
    return <select ref={ref} className={`ui-control ui-select ${className}`.trim()} {...props}>{children}</select>;
  }
);

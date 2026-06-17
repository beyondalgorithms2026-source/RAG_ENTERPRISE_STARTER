import { useState } from "react";

export function useFieldState<T>(initialValue: T, validate?: (value: T) => string) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState("");
  const [touched, setTouched] = useState(false);

  function check(nextValue = value) {
    const nextError = validate?.(nextValue) || "";
    setError(nextError);
    return !nextError;
  }

  function reset(nextValue = initialValue) {
    setValue(nextValue);
    setError("");
    setTouched(false);
  }

  return { value, setValue, error, setError, touched, setTouched, check, reset };
}

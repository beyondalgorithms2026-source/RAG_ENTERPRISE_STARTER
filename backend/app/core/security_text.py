import re
from typing import Any

from app.core.logging import log_event


_INJECTION_PATTERNS = [
    re.compile(r"\bignore (all )?(previous|prior|above) instructions\b", re.I),
    re.compile(r"\bsystem prompt\b", re.I),
    re.compile(r"\bdeveloper message\b", re.I),
    re.compile(r"\bdo not follow\b", re.I),
    re.compile(r"\breveal (the )?(prompt|secret|credentials)\b", re.I),
]


def detect_prompt_injection_signals(text_value: str) -> list[str]:
    text = text_value or ""
    signals: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            signals.append(pattern.pattern)
    return signals


def log_prompt_injection_signals(*, stage: str, text_value: str, metadata: dict[str, Any] | None = None) -> list[str]:
    signals = detect_prompt_injection_signals(text_value)
    if signals:
        log_event(
            "security.prompt_injection_signal",
            stage=stage,
            status="detected",
            reason=";".join(signals[:3]),
            **(metadata or {}),
        )
    return signals

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).with_name("prompt_assets")


def _registry() -> dict[str, Any]:
    payload = json.loads((_ROOT / "registry.json").read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError("Unsupported STARTER prompt registry schema.")
    return payload


def load_prompt(prompt_id: str, *, candidate: bool = False) -> str:
    registry = _registry()
    entry = registry.get("candidates" if candidate else "prompts", {}).get(prompt_id)
    if not isinstance(entry, dict):
        raise RuntimeError(f"Unknown STARTER prompt id: {prompt_id}")
    content = (_ROOT / str(entry["file"])).read_text(encoding="utf-8").rstrip("\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != entry.get("sha256"):
        raise RuntimeError(f"STARTER prompt hash mismatch: {prompt_id}")
    return content


def load_prompt_version(prompt_id: str, version: str) -> str:
    """Load a hash-verified prompt from the registry history by exact version."""
    entry = _registry().get("history", {}).get(prompt_id, {}).get(version)
    if not isinstance(entry, dict):
        raise RuntimeError(f"STARTER prompt {prompt_id} has no registered version {version}")
    content = (_ROOT / str(entry["file"])).read_text(encoding="utf-8").rstrip("\n")
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != entry.get("sha256"):
        raise RuntimeError(f"STARTER prompt hash mismatch: {prompt_id} {version}")
    return content


def prompt_metadata() -> dict[str, dict[str, str]]:
    from app.core.config import settings

    registry = _registry()
    output: dict[str, dict[str, str]] = {}
    pinned = settings.ANSWER_PROMPT_VERSION.strip()
    for prompt_id, entry in registry.get("prompts", {}).items():
        if pinned and prompt_id == "starter_answer":
            load_prompt_version(prompt_id, pinned)
            history = registry["history"][prompt_id][pinned]
            output[prompt_id] = {"version": pinned, "sha256": str(history["sha256"])}
            continue
        candidate = settings.ANSWER_PROMPT_CANDIDATE and prompt_id == "starter_answer"
        if candidate:
            entry = registry.get("candidates", {}).get(prompt_id)
            if not isinstance(entry, dict):
                raise RuntimeError("Candidate STARTER answer prompt is missing.")
        load_prompt(prompt_id, candidate=candidate)
        output[prompt_id] = {
            "version": str(entry["version"]),
            "sha256": str(entry["sha256"]),
        }
    if settings.ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED:
        load_prompt("starter_numeric_claims", candidate=True)
        entry = registry["candidates"]["starter_numeric_claims"]
        output["starter_numeric_claims"] = {
            "version": str(entry["version"]),
            "sha256": str(entry["sha256"]),
        }
    return output

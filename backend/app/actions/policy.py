import re
from typing import Any, Dict, Optional

from app.auth.context import AuthenticatedUser
from app.db.repo_acl import current_acl_context, list_access_summary


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "send_email": {
        "description": "Prepare an outbound email action.",
        "allowed_roles": ["admin", "approver"],
        "allowed_corpora": ["default", "legal", "email_casework"],
        "requires_approval": True,
    },
    "send_slack": {
        "description": "Prepare a Slack message action.",
        "allowed_roles": ["admin", "approver"],
        "allowed_corpora": ["default", "email_casework"],
        "requires_approval": True,
    },
    "create_calendar_event": {
        "description": "Prepare a calendar event action.",
        "allowed_roles": ["admin", "approver"],
        "allowed_corpora": ["default", "email_casework"],
        "requires_approval": True,
    },
    "generate_report": {
        "description": "Generate a placeholder PDF/CSV report artifact.",
        "allowed_roles": ["admin", "approver", "user"],
        "allowed_corpora": ["default", "legal", "transcripts", "db_rows", "email_casework"],
        "requires_approval": False,
    },
}

SENSITIVE_PATTERNS = {
    "compensation": re.compile(r"\b(salary|compensation|bonus|payroll|wage|equity grant)\b", re.I),
    "personal_identifier": re.compile(r"\b(ssn|social security|passport|driver.?s license|dob|date of birth)\b", re.I),
    "secret": re.compile(r"\b(api key|password|secret|token|private key|credential)\b", re.I),
}

SENSITIVE_LABELS = {"confidential", "restricted", "secret", "high"}


def evaluate_tool_policy(*, tool_name: str, actor: Optional[AuthenticatedUser], corpus_name: Optional[str]) -> tuple[bool, str]:
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return False, "unknown_tool"
    actor_roles = {role.lower() for role in (actor.roles if actor else [])}
    allowed_roles = {role.lower() for role in tool["allowed_roles"]}
    if not actor_roles & allowed_roles:
        return False, "role_not_allowed"
    normalized_corpus = (corpus_name or "default").strip() or "default"
    if normalized_corpus not in set(tool["allowed_corpora"]):
        return False, "corpus_not_allowed"
    return True, "allowed"


def detect_sensitive_text(text: str) -> list[str]:
    return [name for name, pattern in SENSITIVE_PATTERNS.items() if pattern.search(text or "")]


def sensitivity_requires_approval(*, question: str, citations: list[Any]) -> tuple[bool, list[str]]:
    reasons = detect_sensitive_text(question)
    for citation in citations:
        label = ""
        if isinstance(citation, dict):
            label = str(citation.get("sensitivity_label") or "")
        else:
            label = str(getattr(citation, "sensitivity_label", "") or "")
        if label.lower() in SENSITIVE_LABELS:
            reasons.append(f"sensitive_corpus:{label.lower()}")
    return bool(reasons), sorted(set(reasons))


def clarification_contract(
    question: str,
    *,
    answer_path: Optional[str],
    evidence_count: int,
    source_scoped: bool = False,
) -> dict[str, Any]:
    lowered = (question or "").lower()
    suggestions = []
    if re.search(r"\b(this|that|it|they|last quarter|recent|latest|soon)\b", lowered):
        suggestions.append("clarify_entity_or_date")
    if re.search(r"\b[a-z]{12,}\b", lowered):
        suggestions.append("check_spelling_or_identifier")
    if '"' in question or "'" in question:
        suggestions.append("try_exact_quote_or_source_scope")
    if answer_path == "not_found" or evidence_count == 0:
        suggestions.append("suggest_source_link_or_upload")
    acl_context = current_acl_context()
    access_limited_possible = False
    if (answer_path == "not_found" or evidence_count == 0) and not acl_context.get("local_dev_full_access"):
        try:
            access_summary = list_access_summary().get("summary") or {}
        except Exception:
            access_summary = {}
        protected_source_count = int(access_summary.get("protected_source_count") or 0)
        exact_lookup_like = bool(
            re.search(r"\b(find|where|show|invoice|salary|policy|contract|customer|case|order|latest|specific)\b", lowered)
            or '"' in question
        )
        access_limited_possible = protected_source_count > 0 and (source_scoped or exact_lookup_like)
    return {
        "clarification_needed": bool(suggestions),
        "suggestions": sorted(set(suggestions)),
        "missing_source_supported": answer_path == "not_found" or evidence_count == 0,
        "access_limited_possible": access_limited_possible,
        "request_access_supported": access_limited_possible,
        "request_access_request_id": None,
        "access_message": (
            "Your current access may limit the documents available for a reliable answer."
            if access_limited_possible
            else None
        ),
    }

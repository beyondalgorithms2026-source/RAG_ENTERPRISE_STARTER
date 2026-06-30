from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from app.core.config import settings


@dataclass(frozen=True)
class AdminModule:
    key: str
    label: str
    href: str
    icon: str
    description: str


ADMIN_MODULES: dict[str, AdminModule] = {
    "overview": AdminModule("overview", "Overview", "/console/admin", "space_dashboard", "System summary and first-run posture."),
    "health": AdminModule("health", "Health", "/console/admin/health", "health_and_safety", "Operational health, coherence, and system posture."),
    "cost": AdminModule("cost", "Cost", "/console/admin/cost", "payments", "Generation cost, token usage, budgets, and price governance."),
    "flywheel": AdminModule("flywheel", "Flywheel", "/console/admin/flywheel", "autorenew", "Feedback-derived evaluation quarantine and review."),
    "embedding": AdminModule("embedding", "Embedding", "/console/admin/embedding", "swap_horiz", "Embedding profile and index-swap lifecycle."),
    "providers": AdminModule("providers", "Providers", "/console/admin/providers", "dns", "Generation providers, models, endpoints, and verification."),
    "uploads": AdminModule("uploads", "Upload Documents", "/console/admin/uploads", "upload_file", "Direct file onboarding and indexing progress."),
    "sources": AdminModule("sources", "Sources", "/console/admin/sources", "description", "Source inventory and source-level controls."),
    "connectors": AdminModule("connectors", "Connectors", "/console/admin/connectors", "hub", "Database connector setup and review."),
    "actions": AdminModule("actions", "Actions", "/console/admin/actions", "approval", "Approvals, tools, and feedback review."),
    "corpora": AdminModule("corpora", "Corpora", "/console/admin/corpora", "folder_shared", "Corpus registry and source assignment."),
    "jobs": AdminModule("jobs", "Jobs", "/console/admin/jobs", "work_history", "Ingestion queue and job controls."),
    "profiles": AdminModule("profiles", "Profiles", "/console/admin/profiles", "account_circle", "Runtime profile activation."),
    "evals": AdminModule("evals", "Evals", "/console/admin/evals", "analytics", "Retrieval quality reports."),
    "traces": AdminModule("traces", "Traces", "/console/admin/traces", "timeline", "Retrieval traces and query debug."),
    "policies": AdminModule("policies", "Policies", "/console/admin/policies", "policy", "Retrieval and corpus policy visibility."),
    "access": AdminModule("access", "Access", "/console/admin/access", "shield_lock", "ACL and access request administration."),
    "audit": AdminModule("audit", "Audit Log", "/console/admin/audit-log", "receipt_long", "Audit and compliance review."),
    "tuning": AdminModule("tuning", "Tuning Lab", "/console/admin/profiles", "tune", "Candidate tuning, cache, and query mining operations."),
    "governance": AdminModule("governance", "Governance", "/console/admin/actions", "gavel", "Restrictions and abuse governance."),
}

SCENARIO_ADMIN_MODULE_PRESETS: dict[str, set[str]] = {
    "research_no_auth": {"overview", "health", "uploads", "sources", "corpora", "jobs", "evals", "traces", "audit"},
    "employee_wide_rag": {"overview", "health", "uploads", "sources", "corpora", "jobs", "evals", "traces", "access", "audit"},
    "small_enterprise_corpus_acl": {"overview", "health", "uploads", "sources", "corpora", "jobs", "access", "evals", "traces", "audit"},
    "enterprise_oidc_acl": set(ADMIN_MODULES.keys()),
}

_PATH_MODULE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/admin/modules", "overview"),
    ("/admin/overview", "overview"),
    ("/admin/health", "health"),
    ("/admin/system", "overview"),
    ("/admin/runtime-settings", "policies"),
    ("/admin/llm", "providers"),
    ("/admin/cost", "cost"),
    ("/admin/embedding", "embedding"),
    ("/admin/retrieval", "tuning"),
    ("/admin/tuning", "tuning"),
    ("/admin/semantic-cache", "tuning"),
    ("/admin/query-mining", "governance"),
    ("/admin/feedback-eval", "flywheel"),
    ("/admin/governance", "governance"),
    ("/admin/retention", "audit"),
    ("/admin/profiles/metadata", "policies"),
    ("/admin/profiles", "profiles"),
    ("/admin/corpora", "corpora"),
    ("/admin/sources", "sources"),
    ("/admin/jobs", "jobs"),
    ("/admin/eval", "evals"),
    ("/admin/traces", "traces"),
    ("/admin/access", "access"),
    ("/admin/audit-log", "audit"),
    ("/admin/approvals", "actions"),
    ("/admin/feedback", "actions"),
    ("/admin/tools", "actions"),
    ("/connectors/db", "connectors"),
)


def active_scenario_profile() -> str:
    value = (settings.SCENARIO_PROFILE or "enterprise_oidc_acl").strip().lower()
    return value if value in SCENARIO_ADMIN_MODULE_PRESETS else "enterprise_oidc_acl"


def enabled_admin_modules() -> set[str]:
    from app.db.repo_runtime_settings import get_setting

    runtime_override = get_setting("admin_modules_enabled")
    if runtime_override is not None:
        return {item for item in runtime_override if item in ADMIN_MODULES} | {"overview"}
    override = (settings.ADMIN_MODULES_ENABLED or "").strip()
    if override:
        requested = {item.strip().lower() for item in override.split(",") if item.strip()}
        return {item for item in requested if item in ADMIN_MODULES} | {"overview"}
    return set(SCENARIO_ADMIN_MODULE_PRESETS[active_scenario_profile()]) | {"overview"}


def admin_modules_source() -> str:
    from app.db.repo_runtime_settings import get_setting

    if get_setting("admin_modules_enabled") is not None:
        return "runtime"
    if (settings.ADMIN_MODULES_ENABLED or "").strip():
        return "environment"
    return "scenario"


def disabled_admin_modules() -> set[str]:
    return set(ADMIN_MODULES) - enabled_admin_modules()


def admin_module_for_path(path: str) -> str | None:
    for prefix, module in _PATH_MODULE_PREFIXES:
        if path == prefix or path.startswith(f"{prefix}/"):
            return module
    return None


def admin_modules_payload() -> dict[str, Any]:
    from app.db.repo_runtime_settings import get_setting

    enabled = enabled_admin_modules()
    scenario = active_scenario_profile()
    runtime_override = get_setting("admin_modules_enabled")
    navigation = [
        {
            "module": module.key,
            "href": module.href,
            "label": module.label,
            "icon": module.icon,
            "description": module.description,
        }
        for key, module in ADMIN_MODULES.items()
        if key in enabled and key != "tuning" and key != "governance"
    ]
    navigation.insert(
        1,
        {
            "module": "overview",
            "href": "/console/admin/modules",
            "label": "Modules",
            "icon": "view_module",
            "description": "Deployment-wide admin console composition.",
        },
    )
    return {
        "scenario_profile": scenario,
        "source": admin_modules_source(),
        "preset_modules": sorted(SCENARIO_ADMIN_MODULE_PRESETS[scenario]),
        "runtime_override": sorted(runtime_override) if runtime_override is not None else None,
        "enabled_modules": sorted(enabled),
        "disabled_modules": sorted(set(ADMIN_MODULES) - enabled),
        "navigation": navigation,
        "modules": [
            {
                "key": module.key,
                "label": module.label,
                "href": module.href,
                "icon": module.icon,
                "description": module.description,
                "enabled": module.key in enabled,
            }
            for module in ADMIN_MODULES.values()
        ],
    }


def ensure_admin_module_enabled(module: str) -> None:
    normalized = module.strip().lower()
    if normalized not in ADMIN_MODULES:
        raise HTTPException(
            status_code=500,
            detail={"error": "unknown_admin_module", "module": normalized},
        )
    if normalized not in enabled_admin_modules():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "module_disabled",
                "module": normalized,
                "scenario_profile": active_scenario_profile(),
                "message": f"Admin module '{normalized}' is disabled for this scenario.",
            },
        )


def enforce_admin_module_for_request(request: Request) -> None:
    module = admin_module_for_path(request.url.path)
    if module:
        ensure_admin_module_enabled(module)

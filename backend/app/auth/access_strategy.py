import hashlib
import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser, get_current_user
from app.auth.service import anonymous_research_enabled, local_dev_auth_enabled
from app.core.config import settings
from app.db.db import engine


SUPPORTED_ACCESS_STRATEGIES = {
    "none",
    "employee_all",
    "corpus_level",
    "document_acl",
    "document_acl_with_time_bound_grants",
}


def active_access_strategy() -> str:
    strategy = (settings.ACCESS_STRATEGY or "document_acl_with_time_bound_grants").strip().lower()
    if strategy not in SUPPORTED_ACCESS_STRATEGIES:
        return "document_acl_with_time_bound_grants"
    return strategy


def local_dev_acl_bypass_enabled(user: Optional[AuthenticatedUser] = None) -> bool:
    principal = user or get_current_user()
    if principal is None or not local_dev_auth_enabled():
        return False
    allowed_ids = {"dev-test-user", "dev-test-admin"}
    allowed_emails = {
        settings.DEV_TEST_USER_EMAIL.strip().lower(),
        settings.DEV_TEST_ADMIN_EMAIL.strip().lower(),
    }
    return principal.user_id in allowed_ids or (principal.email or "").strip().lower() in allowed_emails


def current_access_context() -> dict[str, Any]:
    user = get_current_user()
    return {
        "strategy": active_access_strategy(),
        "external_user_id": user.user_id if user else None,
        "email": user.email if user else None,
        "groups": list(user.groups) if user else [],
        "roles": list(user.roles) if user else [],
        "anonymous_research": anonymous_research_enabled(),
        "local_dev_full_access": local_dev_acl_bypass_enabled(user),
    }


def _identity_email_sql(external_user_param: str, email_param: str) -> str:
    return f"""LOWER(
        COALESCE(
            :{email_param},
            (SELECT au_lookup.email FROM auth_users au_lookup WHERE au_lookup.external_user_id = :{external_user_param} LIMIT 1),
            ''
        )
    )"""


def _document_acl_sql(*, source_alias: str, external_user_param: str) -> str:
    return f"""EXISTS (
        SELECT 1
        FROM auth_users au
        JOIN user_group_memberships ugm ON ugm.user_id = au.id
        JOIN document_acl da ON da.group_id = ugm.group_id
        WHERE au.external_user_id = :{external_user_param}
          AND da.source_id = {source_alias}.id
    )"""


def _direct_grant_sql(*, source_alias: str, external_user_param: str, email_param: str) -> str:
    return f"""EXISTS (
        SELECT 1
        FROM user_source_access_grants usag
        WHERE usag.source_id = {source_alias}.id
          AND usag.revoked_at IS NULL
          AND usag.starts_at <= now()
          AND usag.expires_at > now()
          AND (
            usag.grantee_external_user_id = :{external_user_param}
            OR LOWER(COALESCE(usag.grantee_email, '')) = {_identity_email_sql(external_user_param, email_param)}
          )
    )"""


def _corpus_grant_sql(*, source_alias: str, external_user_param: str, email_param: str) -> str:
    return f"""EXISTS (
        SELECT 1
        FROM corpus_access_grants cag
        LEFT JOIN auth_users au ON au.external_user_id = :{external_user_param}
        LEFT JOIN user_group_memberships ugm ON ugm.user_id = au.id
        WHERE cag.corpus_name = COALESCE({source_alias}.source_metadata_json ->> 'corpus', '')
          AND COALESCE({source_alias}.source_metadata_json ->> 'corpus', '') <> ''
          AND (
            cag.grantee_external_user_id = :{external_user_param}
            OR LOWER(COALESCE(cag.grantee_email, '')) = {_identity_email_sql(external_user_param, email_param)}
            OR cag.group_id = ugm.group_id
          )
    )"""


def source_access_sql(*, params: dict[str, Any], source_alias: str = "s", prefix: str = "access") -> str:
    context = current_access_context()
    strategy = context["strategy"]
    external_user_id = context.get("external_user_id")
    email = context.get("email")
    external_param = f"{prefix}_external_user_id"
    email_param = f"{prefix}_email"
    params[external_param] = external_user_id
    params[email_param] = email

    if strategy == "none":
        return "TRUE" if anonymous_research_enabled() else "FALSE"

    if strategy == "employee_all":
        return "TRUE" if external_user_id else "FALSE"

    if strategy == "corpus_level":
        if not external_user_id:
            return f"{source_alias}.sensitivity_label = 'public'"
        return f"""(
            {source_alias}.sensitivity_label = 'public'
            OR {_corpus_grant_sql(source_alias=source_alias, external_user_param=external_param, email_param=email_param)}
        )"""

    if not external_user_id:
        return f"{source_alias}.sensitivity_label = 'public'"

    clauses = [
        f"{source_alias}.sensitivity_label = 'public'",
        _document_acl_sql(source_alias=source_alias, external_user_param=external_param),
    ]
    if strategy == "document_acl_with_time_bound_grants":
        clauses.append(_direct_grant_sql(source_alias=source_alias, external_user_param=external_param, email_param=email_param))
        if context.get("local_dev_full_access"):
            clauses.append(f"NOT EXISTS (SELECT 1 FROM document_acl da_any WHERE da_any.source_id = {source_alias}.id)")
    return "(\n            " + "\n            OR ".join(clauses) + "\n        )"


def can_current_user_access_source(source_id: int) -> bool:
    params: dict[str, Any] = {"source_id": source_id}
    sql = text(
        f"""
        SELECT EXISTS (
            SELECT 1
            FROM sources s
            WHERE s.id = :source_id
              AND {source_access_sql(params=params, source_alias="s")}
        )
        """
    )
    with engine.connect() as conn:
        return bool(conn.execute(sql, params).scalar())


def active_direct_grant_fingerprint() -> str:
    context = current_access_context()
    external_user_id = context.get("external_user_id")
    email = (context.get("email") or "").strip().lower()
    if not external_user_id:
        return "anonymous"
    sql = text(
        """
        SELECT usag.id, usag.source_id, usag.starts_at, usag.expires_at, COALESCE(usag.grantee_email, '') AS grantee_email
        FROM user_source_access_grants usag
        WHERE usag.revoked_at IS NULL
          AND usag.starts_at <= now()
          AND usag.expires_at > now()
          AND (
            usag.grantee_external_user_id = :external_user_id
            OR LOWER(COALESCE(usag.grantee_email, '')) = LOWER(COALESCE(:email, ''))
            OR LOWER(COALESCE(usag.grantee_email, '')) = LOWER(
                COALESCE((SELECT au.email FROM auth_users au WHERE au.external_user_id = :external_user_id LIMIT 1), '')
            )
          )
        ORDER BY usag.source_id, usag.id
        """
    )
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"external_user_id": external_user_id, "email": email}).mappings().all()]
    payload = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def active_corpus_grant_fingerprint() -> str:
    context = current_access_context()
    external_user_id = context.get("external_user_id")
    email = (context.get("email") or "").strip().lower()
    if not external_user_id:
        return "anonymous"
    sql = text(
        """
        SELECT DISTINCT cag.id, cag.corpus_name, cag.grantee_external_user_id, COALESCE(cag.grantee_email, '') AS grantee_email, ag.name AS group_name
        FROM corpus_access_grants cag
        LEFT JOIN auth_groups ag ON ag.id = cag.group_id
        LEFT JOIN auth_users au ON au.external_user_id = :external_user_id
        LEFT JOIN user_group_memberships ugm ON ugm.user_id = au.id
        WHERE cag.grantee_external_user_id = :external_user_id
           OR LOWER(COALESCE(cag.grantee_email, '')) = LOWER(COALESCE(:email, ''))
           OR LOWER(COALESCE(cag.grantee_email, '')) = LOWER(COALESCE(au.email, ''))
           OR cag.group_id = ugm.group_id
        ORDER BY cag.corpus_name, cag.id
        """
    )
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"external_user_id": external_user_id, "email": email}).mappings().all()]
    payload = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grant_corpus_access(
    *,
    corpus_name: str,
    grantee_external_user_id: Optional[str] = None,
    grantee_email: Optional[str] = None,
    group_name: Optional[str] = None,
) -> None:
    if not corpus_name.strip():
        raise ValueError("corpus_name is required")
    group_id = None
    if group_name and group_name.strip():
        with engine.begin() as conn:
            group_id = conn.execute(
                text(
                    """
                    INSERT INTO auth_groups (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"name": group_name.strip()},
            ).scalar_one()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO corpus_access_grants (corpus_name, grantee_external_user_id, grantee_email, group_id)
                VALUES (:corpus_name, :grantee_external_user_id, :grantee_email, :group_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "corpus_name": corpus_name.strip(),
                "grantee_external_user_id": (grantee_external_user_id or "").strip() or None,
                "grantee_email": (grantee_email or "").strip().lower() or None,
                "group_id": group_id,
            },
        )
    from app.db.repo_semantic_cache import bump_cache_revision

    bump_cache_revision(scope_type="access", reason=f"corpus_grant:{corpus_name}")


def clear_corpus_access_grants(corpus_name: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM corpus_access_grants WHERE corpus_name = :corpus_name"), {"corpus_name": corpus_name.strip()})
    from app.db.repo_semantic_cache import bump_cache_revision

    bump_cache_revision(scope_type="access", reason=f"corpus_grants_cleared:{corpus_name}")

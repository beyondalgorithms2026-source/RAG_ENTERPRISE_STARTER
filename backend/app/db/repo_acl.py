import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser, get_current_user
from app.auth.service import local_dev_auth_enabled
from app.core.config import settings
from app.db.db import engine


def sync_authenticated_user(user: Optional[AuthenticatedUser]) -> None:
    if user is None:
        return

    with engine.begin() as conn:
        principal_id = conn.execute(
            text(
                """
                INSERT INTO auth_users (external_user_id, email, display_name, provider_issuer, user_metadata_json)
                VALUES (:external_user_id, :email, :display_name, :provider_issuer, CAST(:user_metadata_json AS jsonb))
                ON CONFLICT (external_user_id) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    provider_issuer = EXCLUDED.provider_issuer,
                    user_metadata_json = EXCLUDED.user_metadata_json,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "external_user_id": user.user_id,
                "email": user.email,
                "display_name": user.name,
                "provider_issuer": user.issuer,
                "user_metadata_json": json.dumps(
                    {
                        "roles": user.roles,
                        "groups": user.groups,
                        "manager_email": user.raw_claims.get("manager_email") or user.raw_claims.get("managerEmail"),
                        "manager_display_name": user.raw_claims.get("manager_display_name") or user.raw_claims.get("manager_name"),
                        "manager_external_user_id": user.raw_claims.get("manager_external_user_id") or user.raw_claims.get("manager_id"),
                    }
                ),
            },
        ).scalar_one()

        group_ids: list[int] = []
        for group_name in sorted({item.strip() for item in user.groups if item and item.strip()}):
            group_id = conn.execute(
                text(
                    """
                    INSERT INTO auth_groups (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"name": group_name},
            ).scalar_one()
            group_ids.append(int(group_id))

        conn.execute(text("DELETE FROM user_group_memberships WHERE user_id = :user_id"), {"user_id": principal_id})
        for group_id in group_ids:
            conn.execute(
                text(
                    """
                    INSERT INTO user_group_memberships (user_id, group_id)
                    VALUES (:user_id, :group_id)
                    ON CONFLICT (user_id, group_id) DO NOTHING
                    """
                ),
                {"user_id": principal_id, "group_id": group_id},
            )


def current_acl_context() -> dict[str, Any]:
    user = get_current_user()
    return {
        "external_user_id": user.user_id if user else None,
        "groups": list(user.groups) if user else [],
        "roles": list(user.roles) if user else [],
        "local_dev_full_access": local_dev_acl_bypass_enabled(user),
    }


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


def assign_document_acl(*, source_id: int, group_names: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM document_acl WHERE source_id = :source_id"), {"source_id": source_id})
        for group_name in sorted({item.strip() for item in group_names if item and item.strip()}):
            group_id = conn.execute(
                text(
                    """
                    INSERT INTO auth_groups (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"name": group_name},
            ).scalar_one()
            conn.execute(
                text(
                    """
                    INSERT INTO document_acl (source_id, group_id)
                    VALUES (:source_id, :group_id)
                    ON CONFLICT (source_id, group_id) DO NOTHING
                    """
                ),
                {"source_id": source_id, "group_id": int(group_id)},
            )


def list_source_acl_map() -> dict[int, list[str]]:
    sql = text(
        """
        SELECT da.source_id, ag.name
        FROM document_acl da
        JOIN auth_groups ag ON ag.id = da.group_id
        ORDER BY da.source_id ASC, ag.name ASC
        """
    )
    mapping: dict[int, list[str]] = {}
    with engine.connect() as conn:
        for source_id, group_name in conn.execute(sql).fetchall():
            mapping.setdefault(int(source_id), []).append(str(group_name))
    return mapping


def list_access_summary() -> dict[str, Any]:
    from app.db.repo_access_requests import get_active_grant_counts, list_access_requests

    users_sql = text(
        """
        SELECT
            au.external_user_id,
            au.email,
            au.display_name,
            COALESCE(
                jsonb_agg(DISTINCT ag.name) FILTER (WHERE ag.name IS NOT NULL),
                '[]'::jsonb
            ) AS groups,
            au.updated_at
        FROM auth_users au
        LEFT JOIN user_group_memberships ugm ON ugm.user_id = au.id
        LEFT JOIN auth_groups ag ON ag.id = ugm.group_id
        GROUP BY au.id
        ORDER BY au.updated_at DESC, au.external_user_id ASC
        """
    )
    groups_sql = text(
        """
        SELECT
            ag.name,
            COUNT(DISTINCT ugm.user_id)::bigint AS member_count,
            COUNT(DISTINCT da.source_id)::bigint AS source_count
        FROM auth_groups ag
        LEFT JOIN user_group_memberships ugm ON ugm.group_id = ag.id
        LEFT JOIN document_acl da ON da.group_id = ag.id
        GROUP BY ag.id
        ORDER BY ag.name ASC
        """
    )
    source_acl_sql = text(
        """
        SELECT
            s.id,
            s.file_name,
            s.sensitivity_label,
            COALESCE(s.source_metadata_json ->> 'corpus', '') AS corpus_name,
            COALESCE(
                jsonb_agg(DISTINCT ag.name) FILTER (WHERE ag.name IS NOT NULL),
                '[]'::jsonb
            ) AS groups
        FROM sources s
        LEFT JOIN document_acl da ON da.source_id = s.id
        LEFT JOIN auth_groups ag ON ag.id = da.group_id
        GROUP BY s.id
        ORDER BY s.created_at DESC, s.id DESC
        """
    )

    with engine.connect() as conn:
        users = [
            {
                "external_user_id": row.external_user_id,
                "email": row.email,
                "display_name": row.display_name,
                "groups": list(row.groups or []),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in conn.execute(users_sql).mappings().all()
        ]
        groups = [
            {
                "name": row.name,
                "member_count": int(row.member_count or 0),
                "source_count": int(row.source_count or 0),
            }
            for row in conn.execute(groups_sql).mappings().all()
        ]
        source_acl = [
            {
                "source_id": int(row.id),
                "file_name": row.file_name,
                "sensitivity_label": row.sensitivity_label,
                "corpus_name": row.corpus_name or None,
                "groups": list(row.groups or []),
            }
            for row in conn.execute(source_acl_sql).mappings().all()
        ]

    protected_sources = sum(1 for item in source_acl if item["groups"])
    grant_summary = get_active_grant_counts()
    return {
        "users": users,
        "groups": groups,
        "source_acl": source_acl,
        "access_requests": [row.__dict__ for row in list_access_requests(limit=50)],
        "summary": {
            "user_count": len(users),
            "group_count": len(groups),
            "protected_source_count": protected_sources,
            "open_source_count": len(source_acl) - protected_sources,
            "active_grant_count": grant_summary["active_grants"],
            "expired_grant_count": grant_summary["expired_grants"],
        },
    }

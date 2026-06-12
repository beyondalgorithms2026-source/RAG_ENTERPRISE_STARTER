import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text

from app.auth.access_strategy import (
    active_direct_grant_fingerprint,
    can_current_user_access_source,
    current_access_context,
    local_dev_acl_bypass_enabled,
)
from app.auth.context import AuthenticatedUser
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
    return current_access_context()


def upsert_auth_user(
    *,
    external_user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    provider_issuer: Optional[str] = None,
    user_metadata_json: Optional[dict[str, Any]] = None,
) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO auth_users (external_user_id, email, display_name, provider_issuer, user_metadata_json)
                    VALUES (:external_user_id, :email, :display_name, :provider_issuer, CAST(:user_metadata_json AS jsonb))
                    ON CONFLICT (external_user_id) DO UPDATE
                    SET email = COALESCE(EXCLUDED.email, auth_users.email),
                        display_name = COALESCE(EXCLUDED.display_name, auth_users.display_name),
                        provider_issuer = COALESCE(EXCLUDED.provider_issuer, auth_users.provider_issuer),
                        user_metadata_json = CASE
                            WHEN EXCLUDED.user_metadata_json = '{}'::jsonb THEN auth_users.user_metadata_json
                            ELSE EXCLUDED.user_metadata_json
                        END,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "external_user_id": external_user_id,
                    "email": (email or "").strip().lower() or None,
                    "display_name": (display_name or "").strip() or None,
                    "provider_issuer": (provider_issuer or "").strip() or None,
                    "user_metadata_json": json.dumps(user_metadata_json or {}),
                },
            ).scalar_one()
        )


def ensure_group(group_name: str) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
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
        )


def replace_user_memberships(*, external_user_id: str, group_names: list[str]) -> None:
    principal_id = upsert_auth_user(external_user_id=external_user_id)
    cleaned_group_names = sorted({item.strip() for item in group_names if item and item.strip()})
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM user_group_memberships WHERE user_id = :user_id"), {"user_id": principal_id})
        for group_name in cleaned_group_names:
            group_id = ensure_group(group_name)
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
    from app.db.repo_semantic_cache import bump_cache_revision

    bump_cache_revision(scope_type="access", reason=f"user_memberships:{external_user_id}")


def assign_document_acl(*, source_id: int, group_names: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM document_acl WHERE source_id = :source_id"), {"source_id": source_id})
        for group_name in sorted({item.strip() for item in group_names if item and item.strip()}):
            group_id = ensure_group(group_name)
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
    from app.db.repo_semantic_cache import bump_cache_revision

    bump_cache_revision(scope_type="access", reason=f"document_acl:{source_id}")


def replace_source_acl(*, source_id: int, group_names: list[str]) -> None:
    assign_document_acl(source_id=source_id, group_names=group_names)


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


def list_direct_access_grants() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            usag.id,
            usag.source_id,
            s.file_name,
            usag.grantee_external_user_id,
            usag.grantee_email,
            usag.grant_reason,
            usag.starts_at,
            usag.expires_at,
            usag.revoked_at
        FROM user_source_access_grants usag
        JOIN sources s ON s.id = usag.source_id
        ORDER BY usag.created_at DESC, usag.id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [
        {
            "id": int(row.id),
            "source_id": int(row.source_id),
            "file_name": row.file_name,
            "grantee_external_user_id": row.grantee_external_user_id,
            "grantee_email": row.grantee_email,
            "grant_reason": row.grant_reason,
            "starts_at": row.starts_at.isoformat() if row.starts_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "active": bool(row.expires_at and row.expires_at > datetime.now(timezone.utc) and row.revoked_at is None),
        }
        for row in rows
    ]


def explain_source_access(source_id: int) -> dict[str, Any]:
    from app.db.repo_access_requests import list_source_access_contacts

    source_sql = text(
        """
        SELECT
            s.id,
            s.file_name,
            s.sensitivity_label,
            COALESCE(s.source_metadata_json ->> 'corpus', '') AS corpus_name,
            COALESCE(s.source_metadata_json ->> 'source_class', '') AS source_class,
            COALESCE(s.source_metadata_json ->> 'seed_source_key', '') AS seed_source_key
        FROM sources s
        WHERE s.id = :source_id
        """
    )
    membership_sql = text(
        """
        SELECT DISTINCT
            au.external_user_id,
            au.email,
            au.display_name,
            ag.name AS group_name
        FROM document_acl da
        JOIN auth_groups ag ON ag.id = da.group_id
        JOIN user_group_memberships ugm ON ugm.group_id = ag.id
        JOIN auth_users au ON au.id = ugm.user_id
        WHERE da.source_id = :source_id
        ORDER BY ag.name ASC, au.external_user_id ASC
        """
    )
    grant_sql = text(
        """
        SELECT
            grantee_external_user_id,
            grantee_email,
            grant_reason,
            expires_at,
            revoked_at
        FROM user_source_access_grants
        WHERE source_id = :source_id
        ORDER BY created_at DESC, id DESC
        """
    )
    acl_groups = list_source_acl_map().get(int(source_id), [])
    with engine.connect() as conn:
        source = conn.execute(source_sql, {"source_id": source_id}).mappings().first()
        if source is None:
            raise ValueError(f"Source {source_id} not found")
        membership_rows = conn.execute(membership_sql, {"source_id": source_id}).mappings().all()
        grant_rows = conn.execute(grant_sql, {"source_id": source_id}).mappings().all()
    return {
        "source": {
            "source_id": int(source.id),
            "file_name": source.file_name,
            "sensitivity_label": source.sensitivity_label,
            "corpus_name": source.corpus_name or None,
            "source_class": source.source_class or None,
            "seed_source_key": source.seed_source_key or None,
        },
        "acl_groups": acl_groups,
        "group_access": [
            {
                "external_user_id": row.external_user_id,
                "email": row.email,
                "display_name": row.display_name,
                "group_name": row.group_name,
                "reason": f"group:{row.group_name}",
            }
            for row in membership_rows
        ],
        "direct_grants": [
            {
                "grantee_external_user_id": row.grantee_external_user_id,
                "grantee_email": row.grantee_email,
                "grant_reason": row.grant_reason,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            }
            for row in grant_rows
        ],
        "contacts": [row.__dict__ for row in list_source_access_contacts(source_id)],
    }


def explain_user_access(external_user_id: str) -> dict[str, Any]:
    user_sql = text(
        """
        SELECT
            au.external_user_id,
            au.email,
            au.display_name,
            au.user_metadata_json,
            COALESCE(
                jsonb_agg(DISTINCT ag.name) FILTER (WHERE ag.name IS NOT NULL),
                '[]'::jsonb
            ) AS groups
        FROM auth_users au
        LEFT JOIN user_group_memberships ugm ON ugm.user_id = au.id
        LEFT JOIN auth_groups ag ON ag.id = ugm.group_id
        WHERE au.external_user_id = :external_user_id
        GROUP BY au.id
        """
    )
    source_sql = text(
        """
        SELECT DISTINCT
            s.id,
            s.file_name,
            s.sensitivity_label,
            COALESCE(s.source_metadata_json ->> 'corpus', '') AS corpus_name,
            COALESCE(ag.name, '') AS granting_group
        FROM auth_users au
        LEFT JOIN user_group_memberships ugm ON ugm.user_id = au.id
        LEFT JOIN auth_groups ag ON ag.id = ugm.group_id
        LEFT JOIN document_acl da ON da.group_id = ag.id
        LEFT JOIN sources s ON s.id = da.source_id
        WHERE au.external_user_id = :external_user_id
          AND s.id IS NOT NULL
        ORDER BY s.id ASC, granting_group ASC
        """
    )
    grant_sql = text(
        """
        SELECT
            usag.source_id,
            s.file_name,
            usag.grant_reason,
            usag.expires_at,
            usag.revoked_at
        FROM user_source_access_grants usag
        JOIN sources s ON s.id = usag.source_id
        WHERE usag.revoked_at IS NULL
          AND usag.expires_at > now()
          AND usag.grantee_external_user_id = :external_user_id
        ORDER BY usag.expires_at ASC, usag.source_id ASC
        """
    )
    with engine.connect() as conn:
        user = conn.execute(user_sql, {"external_user_id": external_user_id}).mappings().first()
        if user is None:
            raise ValueError(f"User '{external_user_id}' not found")
        sources = conn.execute(source_sql, {"external_user_id": external_user_id}).mappings().all()
        grants = conn.execute(grant_sql, {"external_user_id": external_user_id}).mappings().all()
    return {
        "user": {
            "external_user_id": user.external_user_id,
            "email": user.email,
            "display_name": user.display_name,
            "groups": list(user.groups or []),
            "user_metadata_json": user.user_metadata_json or {},
        },
        "group_access": [
            {
                "source_id": int(row.id),
                "file_name": row.file_name,
                "sensitivity_label": row.sensitivity_label,
                "corpus_name": row.corpus_name or None,
                "reason": f"group:{row.granting_group}",
            }
            for row in sources
        ],
        "direct_grants": [
            {
                "source_id": int(row.source_id),
                "file_name": row.file_name,
                "grant_reason": row.grant_reason,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            }
            for row in grants
        ],
    }


def list_access_summary() -> dict[str, Any]:
    from app.db.repo_access_requests import get_active_grant_counts, list_access_requests, list_source_access_contacts

    users_sql = text(
        """
        SELECT
            au.external_user_id,
            au.email,
            au.display_name,
            au.user_metadata_json,
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
            COALESCE(s.source_metadata_json ->> 'seed_source_key', '') AS seed_source_key,
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
    org_edges_sql = text(
        """
        SELECT
            au.external_user_id,
            au.email,
            COALESCE(au.user_metadata_json ->> 'manager_external_user_id', '') AS manager_external_user_id,
            COALESCE(au.user_metadata_json ->> 'manager_email', '') AS manager_email
        FROM auth_users au
        WHERE COALESCE(au.user_metadata_json ->> 'manager_external_user_id', '') <> ''
           OR COALESCE(au.user_metadata_json ->> 'manager_email', '') <> ''
        ORDER BY au.external_user_id ASC
        """
    )

    with engine.connect() as conn:
        users = [
            {
                "external_user_id": row.external_user_id,
                "email": row.email,
                "display_name": row.display_name,
                "user_metadata_json": row.user_metadata_json or {},
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
                "seed_source_key": row.seed_source_key or None,
                "groups": list(row.groups or []),
            }
            for row in conn.execute(source_acl_sql).mappings().all()
        ]
        org_edges = [
            {
                "external_user_id": row.external_user_id,
                "email": row.email,
                "manager_external_user_id": row.manager_external_user_id or None,
                "manager_email": row.manager_email or None,
            }
            for row in conn.execute(org_edges_sql).mappings().all()
        ]

    protected_sources = sum(1 for item in source_acl if item["groups"])
    grant_summary = get_active_grant_counts()
    source_contacts = []
    for item in source_acl:
        source_contacts.extend([row.__dict__ for row in list_source_access_contacts(item["source_id"])])
    seed_user_count = sum(1 for user in users if (user.get("user_metadata_json") or {}).get("seed_pack"))
    return {
        "users": users,
        "groups": groups,
        "source_acl": source_acl,
        "source_contacts": source_contacts,
        "org_edges": org_edges,
        "direct_grants": list_direct_access_grants(),
        "access_requests": [row.__dict__ for row in list_access_requests(limit=50)],
        "seed_pack_status": {
            "user_count": seed_user_count,
            "source_count": sum(1 for item in source_acl if item.get("seed_source_key")),
            "ready": bool(seed_user_count),
        },
        "summary": {
            "user_count": len(users),
            "group_count": len(groups),
            "protected_source_count": protected_sources,
            "open_source_count": len(source_acl) - protected_sources,
            "active_grant_count": grant_summary["active_grants"],
            "expired_grant_count": grant_summary["expired_grants"],
        },
    }

import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser, get_current_user
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
                "user_metadata_json": json.dumps({"roles": user.roles, "groups": user.groups}),
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
    }


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

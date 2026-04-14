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

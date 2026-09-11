from contextvars import ContextVar, Token
from typing import Any

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = Field(default_factory=lambda: ["user"])
    groups: list[str] = Field(default_factory=list)
    issuer: str | None = None
    raw_claims: dict[str, Any] = Field(default_factory=dict)


_current_user: ContextVar[AuthenticatedUser | None] = ContextVar(
    "authenticated_user", default=None
)


def get_current_user() -> AuthenticatedUser | None:
    return _current_user.get()


def set_current_user(user: AuthenticatedUser | None) -> Token:
    return _current_user.set(user)


def reset_current_user(token: Token) -> None:
    _current_user.reset(token)

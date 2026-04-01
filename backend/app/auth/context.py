from contextvars import ContextVar, Token
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    roles: list[str] = Field(default_factory=lambda: ["user"])
    groups: list[str] = Field(default_factory=list)
    issuer: Optional[str] = None
    raw_claims: dict[str, Any] = Field(default_factory=dict)


_current_user: ContextVar[Optional[AuthenticatedUser]] = ContextVar("authenticated_user", default=None)


def get_current_user() -> Optional[AuthenticatedUser]:
    return _current_user.get()


def set_current_user(user: Optional[AuthenticatedUser]) -> Token:
    return _current_user.set(user)


def reset_current_user(token: Token) -> None:
    _current_user.reset(token)

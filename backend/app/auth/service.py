import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import Request

from app.auth.context import AuthenticatedUser
from app.auth.admin_modules import ADMIN_MODULES, SCENARIO_ADMIN_MODULE_PRESETS
from app.core.config import settings


_CACHE_TTL_S = 300
_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwk_client_cache: dict[str, tuple[float, Any]] = {}


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def auth_enabled() -> bool:
    return auth_required()


def auth_mode() -> str:
    mode = (settings.AUTH_MODE or "").strip().lower()
    if mode:
        return mode
    return "oidc" if settings.AUTH_ENABLED else "none"


def app_env() -> str:
    return (settings.APP_ENV or "local").strip().lower()


def auth_required() -> bool:
    return auth_mode() in {"dev", "password", "oidc"}


def anonymous_research_enabled() -> bool:
    return auth_mode() == "none"


def local_runtime_enabled() -> bool:
    return app_env() in {"local", "dev"}


def local_dev_auth_enabled() -> bool:
    return local_runtime_enabled() and auth_mode() == "dev"


def no_auth_upload_enabled() -> bool:
    return anonymous_research_enabled() and bool(settings.AUTH_NONE_ALLOW_UPLOAD)


def non_local_runtime_enabled() -> bool:
    return app_env() not in {"local", "dev"}


def secure_cookie_required() -> bool:
    return non_local_runtime_enabled() or bool(settings.AUTH_COOKIE_SECURE)


def cookie_samesite_policy() -> str:
    value = (settings.AUTH_COOKIE_SAMESITE or "lax").strip().lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def _is_default_secret(value: str, defaults: set[str]) -> bool:
    return not value or value.strip() in defaults or len(value.strip()) < 32


def _database_password_is_weak(database_url: str) -> bool:
    parsed = urlparse(database_url or "")
    if not parsed.password:
        return True
    return parsed.password in {"password", "postgres", "rag_enterprise_starter_dev_pass"} or len(parsed.password) < 16


def validate_security_posture() -> None:
    mode = auth_mode()
    env = app_env()
    access_strategy = (settings.ACCESS_STRATEGY or "document_acl_with_time_bound_grants").strip().lower()
    scenario_profile = (settings.SCENARIO_PROFILE or "enterprise_oidc_acl").strip().lower()
    admin_modules_override = {item.strip().lower() for item in (settings.ADMIN_MODULES_ENABLED or "").split(",") if item.strip()}
    if mode not in {"none", "dev", "password", "oidc"}:
        raise AuthError("unsupported_auth_mode", f"AUTH_MODE '{mode}' is not supported.", 500)
    if access_strategy not in {"none", "employee_all", "corpus_level", "document_acl", "document_acl_with_time_bound_grants"}:
        raise AuthError("unsupported_access_strategy", f"ACCESS_STRATEGY '{access_strategy}' is not supported.", 500)
    if scenario_profile not in SCENARIO_ADMIN_MODULE_PRESETS:
        raise AuthError("unsupported_scenario_profile", f"SCENARIO_PROFILE '{scenario_profile}' is not supported.", 500)
    unknown_admin_modules = sorted(admin_modules_override - set(ADMIN_MODULES))
    if unknown_admin_modules:
        raise AuthError("unsupported_admin_module", f"ADMIN_MODULES_ENABLED contains unsupported modules: {', '.join(unknown_admin_modules)}.", 500)
    if access_strategy == "none" and mode != "none":
        raise AuthError("unsafe_access_strategy", "ACCESS_STRATEGY=none is allowed only with AUTH_MODE=none.", 500)
    if env in {"staging", "prod", "production"} and mode in {"none", "dev"}:
        raise AuthError("unsafe_auth_mode", f"AUTH_MODE '{mode}' is not allowed when APP_ENV={env}.", 500)
    if mode == "password":
        raise AuthError(
            "password_auth_not_implemented",
            "AUTH_MODE=password is reserved for small-enterprise login but is not implemented yet.",
            500,
        )
    if mode == "dev" and not local_runtime_enabled():
        raise AuthError("dev_auth_not_allowed", "Local dev auth is only available when APP_ENV is local/dev.", 500)
    # These have no source defaults by design. Refuse to start rather than fall
    # back to a value a reader of this repository would already know.
    if mode in {"dev", "oidc"} and not settings.AUTH_STATE_SIGNING_SECRET.strip():
        raise AuthError(
            "missing_auth_state_secret",
            "AUTH_STATE_SIGNING_SECRET is not set. There is no default; set it in backend/.env. "
            'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(48))"',
            500,
        )
    if mode == "dev":
        missing_dev_settings = [
            name
            for name, value in (
                ("DEV_LOCAL_JWT_SECRET", settings.DEV_LOCAL_JWT_SECRET),
                ("DEV_TEST_USER_PASSWORD", settings.DEV_TEST_USER_PASSWORD),
                ("DEV_TEST_ADMIN_PASSWORD", settings.DEV_TEST_ADMIN_PASSWORD),
            )
            if not value.strip()
        ]
        if missing_dev_settings:
            raise AuthError(
                "missing_dev_auth_settings",
                f"AUTH_MODE=dev requires {', '.join(missing_dev_settings)} to be set in backend/.env. "
                "These have no defaults so that no credential ships in source.",
                500,
            )
    if env in {"staging", "prod", "production"}:
        if not settings.FRONTEND_APP_URL.strip().lower().startswith("https://"):
            raise AuthError("https_required", "FRONTEND_APP_URL must use HTTPS in staging/prod.", 500)
        if _database_password_is_weak(settings.DATABASE_URL):
            raise AuthError("weak_database_secret", "DATABASE_URL must include a strong non-default password in staging/prod.", 500)
        if _is_default_secret(
            settings.AUTH_STATE_SIGNING_SECRET,
            {"rag-enterprise-starter-dev-state-secret"},
        ):
            raise AuthError("weak_auth_state_secret", "AUTH_STATE_SIGNING_SECRET must be strong in staging/prod.", 500)
        if _is_default_secret(
            settings.DEV_LOCAL_JWT_SECRET,
            {"rag-enterprise-local-dev-jwt-secret"},
        ):
            raise AuthError("weak_dev_jwt_secret", "DEV_LOCAL_JWT_SECRET must be strong in staging/prod.", 500)
        if mode == "oidc" and _is_default_secret(settings.OIDC_CLIENT_SECRET, {""}):
            raise AuthError("weak_oidc_client_secret", "OIDC_CLIENT_SECRET must be configured in staging/prod OIDC mode.", 500)
        provider = (settings.LLM_PROVIDER or "").strip().lower()
        if provider not in {"ollama", "local", ""} and not (settings.LLM_API_KEY or settings.OLLAMA_API_KEY):
            raise AuthError("missing_llm_api_key", "A provider API key is required for non-local LLM providers in staging/prod.", 500)


def oidc_configured() -> bool:
    return bool(_resolve_discovery_url())


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_discovery_url() -> str:
    if settings.OIDC_DISCOVERY_URL:
        return settings.OIDC_DISCOVERY_URL.strip()
    issuer = settings.OIDC_ISSUER.strip()
    if issuer:
        return f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    return ""


def _cached_get(cache: dict[str, tuple[float, Any]], key: str) -> Optional[Any]:
    entry = cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL_S:
        return entry[1]
    return None


def _cached_set(cache: dict[str, tuple[float, Any]], key: str, value: Any) -> Any:
    cache[key] = (time.time(), value)
    return value


def get_oidc_metadata() -> dict[str, Any]:
    discovery_url = _resolve_discovery_url()
    if not discovery_url:
        raise AuthError("oidc_not_configured", "OIDC discovery URL or issuer is not configured", 503)
    cached = _cached_get(_metadata_cache, discovery_url)
    if cached is not None:
        return cached
    with httpx.Client(timeout=10.0) as client:
        response = client.get(discovery_url)
        response.raise_for_status()
        metadata = response.json()
    return _cached_set(_metadata_cache, discovery_url, metadata)


def _get_jwk_client() -> Any:
    metadata = get_oidc_metadata()
    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise AuthError("oidc_jwks_missing", "OIDC metadata does not contain jwks_uri", 503)
    cached = _cached_get(_jwk_client_cache, jwks_uri)
    if cached is not None:
        return cached
    return _cached_set(_jwk_client_cache, jwks_uri, jwt.PyJWKClient(jwks_uri))


def _audience() -> Optional[str]:
    return settings.OIDC_AUDIENCE.strip() or settings.OIDC_CLIENT_ID.strip() or None


def _allowed_algorithms() -> list[str]:
    return _csv(settings.OIDC_ALLOWED_ALGORITHMS) or ["RS256"]


def _get_roles(claims: dict[str, Any]) -> list[str]:
    raw_value = claims.get(settings.OIDC_ROLE_CLAIM) or claims.get("roles") or claims.get("role") or claims.get("groups")
    extracted: list[str]
    if raw_value is None:
        extracted = []
    elif isinstance(raw_value, str):
        extracted = [raw_value]
    elif isinstance(raw_value, list):
        extracted = [str(item) for item in raw_value]
    else:
        extracted = [str(raw_value)]

    roles = {"user"}
    admin_roles = set(_csv(settings.OIDC_ADMIN_ROLES))
    approver_roles = set(_csv(settings.OIDC_APPROVER_ROLES))
    if admin_roles & set(extracted):
        roles.add("admin")
    if approver_roles & set(extracted):
        roles.add("approver")
    return sorted(roles)


def _get_groups(claims: dict[str, Any]) -> list[str]:
    raw_value = claims.get(settings.OIDC_GROUPS_CLAIM) or claims.get("groups")
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        return [raw_value]
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value if str(item).strip()]
    return [str(raw_value)]


def validate_access_token(token: str) -> AuthenticatedUser:
    if local_dev_auth_enabled():
        return validate_local_dev_token(token)
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        metadata = get_oidc_metadata()
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_allowed_algorithms(),
            audience=_audience(),
            issuer=settings.OIDC_ISSUER.strip() or metadata.get("issuer"),
            options={"require": ["exp", "iat", "sub"]},
        )
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError("invalid_token", f"Token validation failed: {exc}")

    return AuthenticatedUser(
        user_id=str(claims.get("sub")),
        email=claims.get("email"),
        name=claims.get("name") or claims.get("preferred_username"),
        roles=_get_roles(claims),
        groups=_get_groups(claims),
        issuer=claims.get("iss"),
        raw_claims=claims,
    )


def _local_dev_users() -> dict[str, dict[str, Any]]:
    return {
        settings.DEV_TEST_USER_EMAIL.strip().lower(): {
            "password": settings.DEV_TEST_USER_PASSWORD,
            "user": AuthenticatedUser(
                user_id="dev-test-user",
                email=settings.DEV_TEST_USER_EMAIL,
                name=settings.DEV_TEST_USER_NAME,
                roles=["user"],
                groups=["dev-users"],
                issuer=settings.DEV_LOCAL_ISSUER,
                raw_claims={"auth_mode": "dev"},
            ),
        },
        settings.DEV_TEST_ADMIN_EMAIL.strip().lower(): {
            "password": settings.DEV_TEST_ADMIN_PASSWORD,
            "user": AuthenticatedUser(
                user_id="dev-test-admin",
                email=settings.DEV_TEST_ADMIN_EMAIL,
                name=settings.DEV_TEST_ADMIN_NAME,
                roles=["admin", "user"],
                groups=["dev-admins"],
                issuer=settings.DEV_LOCAL_ISSUER,
                raw_claims={"auth_mode": "dev"},
            ),
        },
    }


def authenticate_local_dev_user(email: str, password: str) -> Optional[AuthenticatedUser]:
    candidate = _local_dev_users().get(email.strip().lower())
    if not candidate:
        return None
    if candidate["password"] != password:
        return None
    return candidate["user"]


def build_local_dev_user(
    *,
    user_id: str,
    email: str,
    name: Optional[str] = None,
    roles: Optional[list[str]] = None,
    groups: Optional[list[str]] = None,
    raw_claims: Optional[dict[str, Any]] = None,
) -> AuthenticatedUser:
    normalized_email = email.strip().lower()
    display_name = (name or normalized_email.split("@", 1)[0].replace("-", " ").replace("_", " ").title()).strip() or normalized_email
    normalized_roles = sorted({str(role or "").strip().lower() for role in (roles or ["user"]) if str(role or "").strip()}) or ["user"]
    normalized_groups = sorted({str(group or "").strip() for group in (groups or []) if str(group or "").strip()})
    claims = {"auth_mode": "dev", **(raw_claims or {})}
    return AuthenticatedUser(
        user_id=user_id.strip(),
        email=normalized_email,
        name=display_name,
        roles=normalized_roles,
        groups=normalized_groups,
        issuer=settings.DEV_LOCAL_ISSUER,
        raw_claims=claims,
    )


def issue_local_dev_token(user: AuthenticatedUser) -> str:
    now = int(time.time())
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "groups": user.groups,
        "iss": settings.DEV_LOCAL_ISSUER,
        "iat": now,
        "exp": now + 60 * 60 * 12,
    }
    return jwt.encode(payload, settings.DEV_LOCAL_JWT_SECRET, algorithm="HS256")


def validate_local_dev_token(token: str) -> AuthenticatedUser:
    try:
        claims = jwt.decode(
            token,
            settings.DEV_LOCAL_JWT_SECRET,
            algorithms=["HS256"],
            issuer=settings.DEV_LOCAL_ISSUER,
            options={"require": ["exp", "iat", "sub"], "verify_aud": False},
        )
    except Exception as exc:
        raise AuthError("invalid_token", f"Local dev token validation failed: {exc}")
    return AuthenticatedUser(
        user_id=str(claims.get("sub")),
        email=claims.get("email"),
        name=claims.get("name"),
        roles=[str(item) for item in claims.get("roles", ["user"])],
        groups=[str(item) for item in claims.get("groups", [])],
        issuer=claims.get("iss"),
        raw_claims=claims,
    )


def resolve_post_login_path(user: AuthenticatedUser, next_path: str | None = None) -> str:
    requested = (next_path or "").strip()
    if requested and requested not in {"/", "/console"}:
        return requested
    user_roles = {role.lower() for role in user.roles}
    if "admin" in user_roles or "approver" in user_roles:
        return "/console/admin"
    return "/console/workspace/chat"


def _urlsafe_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _state_secret() -> str:
    return settings.AUTH_STATE_SIGNING_SECRET or settings.OIDC_CLIENT_SECRET or settings.OIDC_CLIENT_ID


def create_state(*, next_path: str) -> str:
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "next_path": next_path,
        "exp": int(time.time()) + 600,
    }
    encoded = _urlsafe_b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _urlsafe_b64(hmac.new(_state_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_state(state: str) -> dict[str, Any]:
    try:
        encoded, signature = state.split(".", 1)
    except ValueError:
        raise AuthError("invalid_state", "OIDC state payload is malformed", 400)
    expected = _urlsafe_b64(hmac.new(_state_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise AuthError("invalid_state", "OIDC state signature is invalid", 400)
    padded = encoded + "=" * (-len(encoded) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise AuthError("expired_state", "OIDC state has expired", 400)
    return payload


def build_login_url(*, next_path: str) -> tuple[str, str]:
    metadata = get_oidc_metadata()
    authorization_endpoint = metadata.get("authorization_endpoint")
    if not authorization_endpoint:
        raise AuthError("oidc_authorization_missing", "OIDC metadata does not contain authorization_endpoint", 503)
    state = create_state(next_path=next_path)
    query = urlencode(
        {
            "client_id": settings.OIDC_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.OIDC_REDIRECT_URI,
            "scope": settings.OIDC_SCOPES,
            "state": state,
        }
    )
    return f"{authorization_endpoint}?{query}", state


def exchange_code_for_token(code: str) -> dict[str, Any]:
    metadata = get_oidc_metadata()
    token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        raise AuthError("oidc_token_missing", "OIDC metadata does not contain token_endpoint", 503)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "client_id": settings.OIDC_CLIENT_ID,
    }
    if settings.OIDC_CLIENT_SECRET:
        data["client_secret"] = settings.OIDC_CLIENT_SECRET
    with httpx.Client(timeout=10.0) as client:
        response = client.post(token_endpoint, data=data)
        response.raise_for_status()
        return response.json()


def token_from_request(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    return cookie_token.strip() if cookie_token else None


def authenticate_request(request: Request) -> Optional[AuthenticatedUser]:
    if not auth_enabled():
        return None
    token = token_from_request(request)
    if not token:
        return None
    return validate_access_token(token)

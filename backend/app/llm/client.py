from app.core.config import settings
from app.core.logging import logger


_llm_ready = False


def is_llm_ready() -> bool:
    return _llm_ready


def _get_httpx():
    try:
        import httpx
    except ImportError:
        return None
    return httpx


def _auth_headers(api_key: str = "") -> dict:
    key = api_key or getattr(settings, "OLLAMA_API_KEY", None) or getattr(settings, "LLM_API_KEY", None)
    if not key:
        return {"Content-Type": "application/json"}
    return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}


def verify_llm_ready():
    global _llm_ready
    from app.profiles.resolver import get_effective_llm
    from app.llm.providers import get_provider

    llm = get_effective_llm()
    httpx = _get_httpx()
    if httpx is None:
        logger.error("httpx is not installed; LLM preflight is unavailable during M2 smoke checks.")
        _llm_ready = False
        return False

    try:
        provider = get_provider(llm.provider)
        base = llm.base_url.rstrip("/")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(provider.models_url(base), headers=provider.headers(llm, _auth_headers(llm.api_key)))
            if response.status_code != 200:
                logger.error(f"LLM preflight: model listing at {base} returned HTTP {response.status_code}")
                _llm_ready = False
                return False
            if not provider.verify_models(response.json(), llm.model):
                logger.error(f"LLM preflight: model '{llm.model}' not found at {base} (provider {provider.name}).")
                _llm_ready = False
                return False
        logger.info(f"LLM preflight OK: {llm.model} ready via provider {provider.name}.")
        _llm_ready = True
        return True
    except Exception as exc:
        logger.error(f"LLM Preflight failed: {exc}")
        _llm_ready = False
        return False


def _provider_generate(llm, system_prompt: str, user_prompt: str, *, json_mode: bool, temperature: float, max_tokens, timeout_s: float) -> dict:
    """Single provider-dispatched completion path used by both answer and
    transform generation (AR9)."""
    from app.llm.providers import get_provider

    httpx = _get_httpx()
    if httpx is None:
        return {"success": False, "error": "httpx is not installed."}
    try:
        provider = get_provider(llm.provider)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    base = llm.base_url.rstrip("/")
    headers = provider.headers(llm, _auth_headers(llm.api_key))
    effective_json = json_mode and provider.supports_native_json
    payload = provider.build_payload(
        llm, system_prompt, user_prompt, json_mode=effective_json, temperature=temperature, max_tokens=max_tokens
    )
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(provider.chat_url(base), json=payload, headers=headers)
            response.raise_for_status()
            return {"success": True, "content": provider.extract_content(response.json()) or ""}
    except httpx.TimeoutException:
        return {"success": False, "error": f"LLM provider timeout ({timeout_s}s).", "timeout": True}
    except Exception as exc:
        logger.error(f"LLM generation failed (provider {llm.provider}): {exc}")
        return {"success": False, "error": str(exc)}


def generate_transform_text(system_prompt: str, user_prompt: str, *, timeout_s: float, max_tokens: int = 256) -> dict:
    """Short-timeout, plain-text completion for query transformation (AR5).

    Unlike generate_answer (which floors the timeout at 300s for answer
    generation), this honors the caller's small transform budget so a slow or
    unreachable LLM falls back to the original query quickly. Provider-dispatched
    (AR9); plain text, not JSON.
    """
    from app.profiles.resolver import get_effective_llm

    llm = get_effective_llm()
    return _provider_generate(
        llm, system_prompt, user_prompt, json_mode=False, temperature=0.0, max_tokens=max_tokens, timeout_s=max(0.05, float(timeout_s))
    )


def generate_answer(system_prompt: str, user_prompt: str) -> dict:
    from app.profiles.resolver import get_effective_llm

    llm = get_effective_llm()
    prompt_json_only = llm.structured_output_mode == "prompt_json_only"
    timeout_s = max(float(llm.timeout_s or 300), 300.0)
    return _provider_generate(
        llm,
        system_prompt,
        user_prompt,
        json_mode=not prompt_json_only,
        temperature=0.0 if prompt_json_only else llm.temperature,
        max_tokens=llm.max_tokens,
        timeout_s=timeout_s,
    )

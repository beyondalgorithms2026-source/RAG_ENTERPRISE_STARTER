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
    llm = get_effective_llm()
    httpx = _get_httpx()
    if httpx is None:
        logger.error("httpx is not installed; LLM preflight is unavailable during M2 smoke checks.")
        _llm_ready = False
        return False

    try:
        base = llm.base_url.rstrip("/")
        if llm.provider == "ollama":
            url = f"{base}/v1/models"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch models from {base}. HTTP {response.status_code}")
                    _llm_ready = False
                    return False

                data = response.json()
                models = data.get("models") or data.get("data") or []
                model_ids = [model.get("id") or model.get("name") for model in models]
                if not any(llm.model in (model_id or "") for model_id in model_ids):
                    logger.error(f"Model '{llm.model}' not found in Ollama at {base}")
                    _llm_ready = False
                    return False

                logger.info(f"LLM Preflight matched (local): {llm.model} is ready.")
                _llm_ready = True
                return True

        if llm.provider == "ollama_cloud":
            url = f"{base}/tags"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=_auth_headers(llm.api_key))
                if response.status_code != 200:
                    logger.error(f"Failed to fetch cloud tags from {base}. HTTP {response.status_code}")
                    _llm_ready = False
                    return False

                data = response.json()
                models = data.get("models", [])
                model_names = [model.get("name") for model in models if isinstance(model, dict)]
                if model_names and not any(llm.model in (name or "") for name in model_names):
                    logger.warning(f"Cloud tags reachable but model '{llm.model}' not listed. Continuing as ready.")

                logger.info("LLM Preflight OK (cloud): endpoint reachable.")
                _llm_ready = True
                return True

        logger.error(f"Unknown LLM_PROVIDER='{llm.provider}'.")
        _llm_ready = False
        return False
    except Exception as exc:
        logger.error(f"LLM Preflight failed: {exc}")
        _llm_ready = False
        return False


def generate_answer(system_prompt: str, user_prompt: str) -> dict:
    from app.profiles.resolver import get_effective_llm
    llm = get_effective_llm()
    httpx = _get_httpx()
    if httpx is None:
        return {"success": False, "error": "httpx is not installed."}

    base = llm.base_url.rstrip("/")
    headers = _auth_headers(llm.api_key)
    timeout_s = float(llm.timeout_s or 300)
    timeout_s = max(timeout_s, 300.0)

    if llm.provider == "ollama":
        url = f"{base}/v1/chat/completions"
        payload = {
            "model": llm.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": llm.temperature,
            "response_format": {"type": "json_object"},
        }
        if llm.max_tokens is not None:
            payload["max_tokens"] = llm.max_tokens
        try:
            with httpx.Client(timeout=timeout_s) as client:
                logger.info(f"Sending LOCAL LLM request to {url} with model {llm.model}")
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return {"success": True, "content": content}
        except httpx.TimeoutException:
            logger.error(f"LOCAL LLM generation timed out after {timeout_s}s.")
            return {"success": False, "error": f"LLM provider timeout ({timeout_s}s)."}
        except Exception as exc:
            logger.error(f"LOCAL LLM generation failed: {exc}")
            return {"success": False, "error": str(exc)}

    if llm.provider == "ollama_cloud":
        url = f"{base}/chat"
        payload = {
            "model": llm.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": llm.temperature},
        }
        try:
            with httpx.Client(timeout=timeout_s) as client:
                logger.info(f"Sending CLOUD LLM request to {url} with model {llm.model}")
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = (data.get("message") or {}).get("content", "")
                return {"success": True, "content": content}
        except httpx.TimeoutException:
            logger.error(f"CLOUD LLM generation timed out after {timeout_s}s.")
            return {"success": False, "error": f"LLM provider timeout ({timeout_s}s)."}
        except Exception as exc:
            logger.error(f"CLOUD LLM generation failed: {exc}")
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": f"Unknown LLM_PROVIDER='{llm.provider}'"}

"""Custom / Ollama (local) provider profile.

Covers any endpoint registered as provider="custom", including local
Ollama instances and OpenAI-compatible reasoning endpoints (GLM-5.2 on
Volcengine ARK, vLLM, llama.cpp). Key quirks:
  - ollama_num_ctx → extra_body.options.num_ctx (local context window)
  - reasoning_config disabled → top-level reasoning_effort="none"
    (Ollama /v1/chat/completions ignores think=False — ollama#14820)
    + extra_body.think = False when the backend accepts it
  - reasoning_config enabled + effort → top-level reasoning_effort
    (the native OpenAI-compatible format GLM/ARK expect; unset omits it
    so the endpoint's server default applies)
  - max_tokens capped to real per-model limits when base_url is actually
    OpenAI's hosted API rather than a local/Ollama-style relay
"""

from typing import Any

from agent.model_metadata import get_openai_direct_max_completion_tokens
from providers import register_provider
from providers.base import ProviderProfile


def _points_at_real_openai(base_url: Any) -> bool:
    """True when base_url is OpenAI's actual hosted API, not a local relay.

    "custom" is a generic alias — it covers local/Ollama-style servers AND
    real hosted OpenAI-compatible endpoints under one provider name. The two
    have very different hard limits, so callers that need to know which real
    backend they're talking to (e.g. get_max_tokens()) use this check.
    """
    s = str(base_url or "").strip().lower()
    return "api.openai.com" in s


def _accepts_reasoning_effort_top_level(base_url: Any) -> bool:
    """Gate top-level reasoning_effort to backends that understand it.

    Official OpenAI Chat Completions (api.openai.com) and Azure OpenAI reject
    reasoning_effort on standard chat models (HTTP 400 — same class of bug as
    extra_body.think). Ollama, GLM/ARK, vLLM, and other OpenAI-compatible
    relays may require it (#25758). Powerunits routes primary chat through
    provider=custom + api.openai.com — see docs/powerunits_openai_request_compatibility_v1.md.
    """
    s = str(base_url or "").strip().lower()
    if not s:
        return True
    if "api.openai.com" in s:
        return False
    if "openai.azure.com" in s:
        return False
    return True


def _accepts_ollama_think_extra_body(base_url: Any) -> bool:
    """Gate extra_body["think"] (Ollama extension) to servers that support it.

    Official OpenAI Chat Completions and Azure OpenAI reject unknown body
    keys and return HTTP 400 ("Unrecognized request argument supplied:
    think") — including boolean false. Some deployments register those
    endpoints under provider="custom" (or an alias like "local"), so this
    profile must not assume every "custom" backend is Ollama-compatible.

    Kept as a local copy (rather than importing from
    agent/transports/chat_completions.py) to avoid a provider-plugin ->
    transport layering dependency; see the legacy-path copy there for the
    call site that predates the ProviderProfile architecture.
    """
    s = str(base_url or "").strip().lower()
    if not s:
        # Indeterminate URL (e.g. unit tests); keep legacy behavior.
        return True
    if "api.openai.com" in s:
        return False
    if "openai.azure.com" in s:
        return False
    return True


class CustomProfile(ProviderProfile):
    """Custom/Ollama local provider — think=false and num_ctx support."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        ollama_num_ctx: int | None = None,
        base_url: Any = None,
        **ctx: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        # Ollama context window
        if ollama_num_ctx:
            options = extra_body.get("options", {})
            options["num_ctx"] = ollama_num_ctx
            extra_body["options"] = options

        # Reasoning / thinking control for custom OpenAI-compatible endpoints
        # (GLM-5.2 on Volcengine ARK, vLLM, Ollama, llama.cpp, …).
        #
        #   - disabled  → top-level reasoning_effort="none" plus
        #     extra_body.think = False when the backend accepts it
        #   - enabled + effort set → TOP-LEVEL reasoning_effort string
        #   - enabled + no effort  → omit both, server default applies
        if reasoning_config and isinstance(reasoning_config, dict):
            _effort = (reasoning_config.get("effort") or "").strip().lower()
            _enabled = reasoning_config.get("enabled", True)
            if not _accepts_reasoning_effort_top_level(base_url):
                pass  # OpenAI/Azure direct: omit reasoning_effort entirely
            elif _effort == "none" or _enabled is False:
                # Ollama's /v1/chat/completions silently ignores
                # extra_body.think (only /api/chat honours it — ollama#14820)
                # but respects the top-level reasoning_effort field, so both
                # are needed to actually stop a thinking-capable model from
                # reasoning (#25758). Gate think=False to backends that accept
                # it — official OpenAI/Azure reject the unknown key (HTTP 400).
                top_level["reasoning_effort"] = "none"
                if _accepts_ollama_think_extra_body(base_url):
                    extra_body["think"] = False
            elif _effort:
                top_level["reasoning_effort"] = _effort

        return extra_body, top_level

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Custom/Ollama: base_url is user-configured; fetch if set."""
        if not (base_url or self.base_url):
            return None
        return super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)

    def get_max_tokens(self, model: str | None, *, base_url: Any = None) -> int | None:
        """Cap max_tokens to OpenAI's real per-model limit on direct OpenAI.

        default_max_tokens=65536 (below) is deliberately generous for
        local/Ollama-style backends. Real OpenAI enforces much lower hard
        per-model caps and rejects anything higher with HTTP 400 (e.g.
        gpt-4.1-mini supports at most 32768 completion tokens) — which
        error_classifier.py's broad _CONTEXT_OVERFLOW_PATTERNS then
        misclassifies as context_overflow, causing a spurious "Cannot
        compress further" session reset on what may be a brand-new, tiny
        session. See docs/powerunits_primary_provider_routing_v1.md.
        """
        if _points_at_real_openai(base_url):
            cap = get_openai_direct_max_completion_tokens(model)
            if cap is not None:
                return cap
        return self.default_max_tokens


custom = CustomProfile(
    name="custom",
    aliases=(
        "ollama",
        "local",
        "vllm",
        "llamacpp",
        "llama.cpp",
        "llama-cpp",
    ),
    env_vars=(),  # No fixed key — custom endpoint
    base_url="",  # User-configured
    # Without this, no max_tokens is sent and Ollama falls back to its internal
    # num_predict=128, truncating responses after a few tokens (#39281). This is
    # only a floor used when the user hasn't set model.max_tokens — they can
    # override per-model — so we set it generously rather than lowballing it.
    default_max_tokens=65536,
)

register_provider(custom)

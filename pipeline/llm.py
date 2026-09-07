"""LLM transport for the pipeline.

This is the ONE legacy import (REBUILD.md: `agent/` is read-only reference
— "import from it, never edit"). The Client is pure transport plumbing —
OpenAI-compatible chat with vision parts, per-model dialect adaptation,
rate-limit patience, empty-content budget escalation, JSON repair loops —
hardened over 100+ runs. None of it is agent logic; re-typing it would
only fork its bugfixes. Everything the pipeline DECIDES lives in pipeline/.
"""
import os

from agent.llm import Client, LLMError  # noqa: F401  (transport only)


_REASONING_INSTALLED = False


def _install_reasoning_effort():
    """REASONING EFFORT ON EVERY CALL (owner 2026-09-09: 'make sure we are
    addressing this LLM issue properly' — the model exposes a reasoning
    effort setting and the pipeline never set it, so every card ran at
    the default). The transport in agent/ is read-only reference, so the
    setting rides on the request at the HTTP seam: LLM_REASONING (default
    'medium'; 'none' disables) is added to the JSON body of chat calls."""
    global _REASONING_INSTALLED
    if _REASONING_INSTALLED:
        return
    effort = (os.environ.get("LLM_REASONING") or "medium").strip().lower()
    if effort in ("", "none", "off", "0"):
        _REASONING_INSTALLED = True
        return
    import agent.llm as _transport
    _post = _transport.requests.post

    def post(url, *a, **kw):
        body = kw.get("json")
        if isinstance(body, dict) and "messages" in body and "reasoning" not in body:
            body = dict(body, reasoning={"effort": effort})
            kw["json"] = body
        return _post(url, *a, **kw)
    _transport.requests.post = post
    _REASONING_INSTALLED = True


def make_client(temperature=0.1, max_output_tokens=14000):
    """The run engine from the environment (LLM_BASE_URL / LLM_API_KEY /
    LLM_MODEL) — pure gpt-5.6-luna in dispatched runs per the standing
    directive; the env decides, code does not."""
    _install_reasoning_effort()
    return Client(temperature=temperature, max_output_tokens=max_output_tokens)


def env_ready():
    return all(os.environ.get(k) for k in
               ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))

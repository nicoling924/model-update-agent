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
_EFFORT = None            # the stage's own effort, set by the run; None = the env's


def set_reasoning(effort, log=None):
    """THE STAGE CHOOSES HOW HARD TO THINK (owner 2026-09-17: a mapping turn
    that reads a printed face and writes what it says is not the same work as
    the review's reasoning about a break — and at two minutes a turn the
    mapping never finished the model). Takes effect on the next call."""
    global _EFFORT
    _EFFORT = (str(effort).strip().lower() or None) if effort else None
    if log:
        log(f"[llm] reasoning effort for this stage: {_EFFORT or 'the environment default'}")
    return _EFFORT


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
            body = dict(body, reasoning={"effort": _EFFORT or effort})
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


class BrainUnavailable(RuntimeError):
    """The engine refused the run before it started (no credits, bad key)."""


def handshake(client, post=None):
    """THE BRAIN HANDSHAKE (owner 2026-09-15, after run 34925710395 ran an
    hour without a brain: OpenRouter answered 402 'requires more credits'
    four minutes in and every later card went unanswered). One tiny call
    before the model is touched, shaped like the run's own calls — the
    same output budget, because the aggregator prices affordability on
    max_tokens, so a smaller probe would pass while the run fails.
    401/402/403 -> BrainUnavailable with the server's own words; a
    transient fault is left to the transport's patience."""
    import agent.llm as _transport
    post = post or _transport.requests.post
    body = {"model": client.model, "temperature": 0,
            "max_tokens": client.max_output_tokens,
            "messages": [{"role": "user", "content": "Reply with the single word: ready"}]}
    try:
        r = post(f"{client.base_url}/chat/completions",
                 headers={"Authorization": f"Bearer {client.api_key}"}, json=body, timeout=120)
    except Exception as e:  # noqa: BLE001 — network hiccup: the run's own patience decides
        return f"handshake skipped ({e})"
    if r.status_code in (401, 402, 403):
        try:
            msg = (r.json().get("error") or {}).get("message") or r.text[:300]
        except Exception:  # noqa: BLE001
            msg = r.text[:300]
        raise BrainUnavailable(f"{r.status_code} from {client.base_url}: {msg}")
    return f"ready ({r.status_code})"


def env_ready():
    return all(os.environ.get(k) for k in
               ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))

"""Minimal OpenAI-compatible chat client. The ONLY module that talks to an LLM.

Every call: system prompt + task prompt -> JSON, schema-validated in code, with
bounded repair retries. No streaming, no tools, no agent loop — the harness owns
control flow, so a weaker model cannot wander.
"""
import json
import os
import re
import time

import requests


class LLMError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url=None, api_key=None, model=None,
                 temperature=0.1, max_output_tokens=8000):
        self.base_url = (base_url or os.environ["LLM_BASE_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["LLM_API_KEY"]
        self.model = model or os.environ["LLM_MODEL"]
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.deadline = None      # monotonic run deadline (pipeline.run sets it); None = unbounded
        # provenance: every call's model + token usage, surfaced in the run report
        self.usage = {"model": self.model, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    @classmethod
    def reviewer(cls, cfg):
        """Reviewer client — falls back to the updater endpoint if unset."""
        return cls(
            base_url=os.environ.get("REVIEWER_BASE_URL") or None,
            api_key=os.environ.get("REVIEWER_API_KEY") or None,
            model=os.environ.get("REVIEWER_MODEL") or None,
            temperature=cfg["reviewer"]["temperature"],
            max_output_tokens=cfg["reviewer"]["max_output_tokens"],
        )

    def chat(self, system, user, force_json=True, images=None):
        # images: [(mime, base64), ...] -> OpenAI-compatible vision content parts
        content = user if not images else (
            [{"type": "text", "text": user}]
            + [{"type": "image_url",
                "image_url": {"url": f"data:{m};base64,{b}"}} for m, b in images])
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": content}],
        }
        if force_json:
            body["response_format"] = {"type": "json_object"}
        last_err = None
        for attempt in range(10):
            # THE RUN CLOCK: past the deadline no attempt starts; near it the
            # socket timeout shrinks to what is left (audit 2026-09-14: one
            # call could retry for an hour, the run had no clock)
            left = None if self.deadline is None else self.deadline - time.monotonic()
            if left is not None and left <= 0:
                raise LLMError(f"run deadline passed before the call ({last_err or 'no attempt made'})")
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body, timeout=600 if left is None else max(30, min(600, left)))
                if r.status_code == 400:
                    # adapt to per-model parameter dialects, one change per pass
                    err = (r.json().get("error") or {}) if r.headers.get(
                        "content-type", "").startswith("application/json") else {}
                    param, msg = err.get("param"), err.get("message", r.text[:300])
                    last_err = f"400: {msg}"
                    if param == "max_tokens" and "max_tokens" in body:
                        body["max_completion_tokens"] = body.pop("max_tokens")
                        continue
                    if param and param in body:
                        body.pop(param)  # model dialect rejects it; drop and retry
                        continue
                    if "response_format" in body:
                        body.pop("response_format")  # no JSON mode; prompt still demands JSON
                        continue
                    raise LLMError(f"LLM request rejected: {msg}")
                r.raise_for_status()
                data = r.json()
                if not data.get("choices"):
                    # aggregators can return 200 with an error body (provider
                    # hiccup, rate limit, credit issue) — treat as retryable
                    msg = str((data.get("error") or {}).get("message", data))[:300]
                    last_err = f"no-choices response: {msg}"
                    slow = any(w in msg.lower() for w in ("rate", "quota", "credit", "capacity"))
                    time.sleep(min(30 * (attempt + 1), 120) if slow else 5 * (attempt + 1))
                    continue
                u = data.get("usage") or {}
                self.usage["calls"] += 1
                self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
                self.usage["completion_tokens"] += u.get("completion_tokens", 0)
                self.usage["model"] = data.get("model", self.model)  # server-reported model id
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
                if not content.strip():
                    # reasoning models can burn the whole budget thinking; escalate once per pass
                    cap = body.get("max_completion_tokens") or body.get("max_tokens") or 0
                    if cap and cap < 64000:
                        key = "max_completion_tokens" if "max_completion_tokens" in body else "max_tokens"
                        body[key] = min(cap * 2, 64000)
                        last_err = (f"empty content (finish={choice.get('finish_reason')}); "
                                    f"raising output budget to {body[key]}")
                        continue
                    raise LLMError(f"empty content at max budget (finish={choice.get('finish_reason')})")
                return content
            except requests.RequestException as e:
                resp = getattr(e, "response", None)
                detail = getattr(resp, "text", "")[:300]
                last_err = f"{e} {detail}"
                if resp is not None and resp.status_code == 429:
                    # tokens-per-minute window: wait it out patiently
                    time.sleep(min(30 * (attempt + 1), 120))
                    continue
                if attempt == 5:
                    raise LLMError(f"LLM call failed: {last_err}") from e
                time.sleep(5 * (attempt + 1))
        raise LLMError(f"LLM call failed: {last_err}")

    def json(self, system, user, validate, repair_retries=2, images=None):
        """Call, parse JSON, run `validate(obj) -> list[str] of errors`.
        On parse/validation failure, re-ask once per retry with the errors quoted."""
        prompt = user
        for attempt in range(repair_retries + 1):
            raw = self.chat(system, prompt, images=images)
            try:
                obj = json.loads(_strip_fences(raw))
            except json.JSONDecodeError as e:
                errs = [f"Response was not valid JSON: {e}"]
            else:
                errs = validate(obj)
                if not errs:
                    return obj
            if attempt < repair_retries:
                prompt = (user + "\n\nYour previous answer failed validation:\n- "
                          + "\n- ".join(errs[:20])
                          + "\nReturn corrected JSON only.")
        from pathlib import Path
        dbg = Path(".cache/last_failed_response.txt")
        dbg.parent.mkdir(parents=True, exist_ok=True)
        dbg.write_text(raw)
        raise LLMError("LLM output failed validation after retries: " + "; ".join(errs[:5])
                       + f" (raw response saved to {dbg})")


def _strip_fences(s):
    """The JSON the model meant, out of the reply it actually sent: a fenced
    block, or — when it wrote a sentence first, as Luna habitually does — the
    first BALANCED {...} object in the text. Prose around the answer is a
    habit, not a refusal; it used to abort the whole exchange."""
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    if m:
        return m.group(1)
    try:
        json.loads(s)
        return s
    except ValueError:
        pass
    start = s.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                in_str, esc = (in_str and not (c == '"' and not esc)), (c == "\\" and not esc)
                continue
            if c == '"':
                in_str, esc = True, False
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        start = s.find("{", start + 1)
    return s

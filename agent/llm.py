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

    def chat(self, system, user, force_json=True):
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if force_json:
            body["response_format"] = {"type": "json_object"}
        last_err = None
        for attempt in range(10):
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body, timeout=600)
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

    def json(self, system, user, validate, repair_retries=2):
        """Call, parse JSON, run `validate(obj) -> list[str] of errors`.
        On parse/validation failure, re-ask once per retry with the errors quoted."""
        prompt = user
        for attempt in range(repair_retries + 1):
            raw = self.chat(system, prompt)
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
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s

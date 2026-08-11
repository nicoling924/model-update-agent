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
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body, timeout=600)
                if r.status_code == 400 and force_json and "response_format" in body:
                    body.pop("response_format")  # endpoint lacks JSON mode; prompt still demands JSON
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except requests.RequestException as e:
                if attempt == 2:
                    raise LLMError(f"LLM call failed: {e}") from e
                time.sleep(5 * (attempt + 1))

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
        raise LLMError("LLM output failed validation after retries: " + "; ".join(errs[:5]))


def _strip_fences(s):
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s

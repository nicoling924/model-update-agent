"""RELAY MODE (owner side experiment, 2026-08-26): the engine's judgment
questions are answered by an EXTERNAL brain — Copilot Studio's built-in
GPT — instead of a direct LLM API call.

The engine is unchanged: it queues each bounded question to disk, the
Studio flow collects it (GET /questions), runs a Prompt action on the
built-in GPT, posts the JSON back (POST /questions/{id}/answer), and the
engine's referee checks the answer exactly as it checks any engine's.
Judgment stays with a model; guards stay with code; only the phone line
changed.

Limitations by design (test version): vision questions are declined
(Studio prompt actions can't reliably carry our page images), so reading
falls back to text-only channels; each question waits up to
RELAY_TIMEOUT seconds for Studio's flow to answer.
"""
import json
import time
import uuid
from pathlib import Path

RELAY_DIR = Path(__file__).resolve().parent.parent / "runs" / "relay"
RELAY_TIMEOUT = 1800          # seconds per question
POLL = 3


class RelayTimeout(RuntimeError):
    pass


class RelayClient:
    """Drop-in for llm.Client: same .json() contract, answers arrive
    from whoever is working the queue (Studio's flow — or any tester)."""

    def __init__(self, timeout=RELAY_TIMEOUT):
        self.timeout = timeout
        self.usage = {"model": "relay(studio-gpt)", "questions": 0}
        RELAY_DIR.mkdir(parents=True, exist_ok=True)

    def chat(self, system, user, force_json=True, images=None):
        if images:
            raise RuntimeError("relay mode carries no images — "
                               "vision channel unavailable")
        qid = uuid.uuid4().hex[:12]
        qp = RELAY_DIR / f"{qid}.question.json"
        ap = RELAY_DIR / f"{qid}.answer.json"
        qp.write_text(json.dumps({
            "id": qid, "created": time.time(),
            "system": system, "user": user,
            "instructions": ("Answer with ONE JSON object only, per the "
                             "task in 'user'. No prose around it.")},
            ensure_ascii=False))
        self.usage["questions"] += 1
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            if ap.exists():
                raw = json.loads(ap.read_text()).get("answer", "")
                qp.unlink(missing_ok=True)
                ap.unlink(missing_ok=True)
                return raw
            time.sleep(POLL)
        qp.unlink(missing_ok=True)
        raise RelayTimeout(f"no answer for question {qid} within "
                           f"{self.timeout}s — is the Studio flow running?")

    def json(self, system, user, validate, repair_retries=2, images=None):
        prompt = user
        for attempt in range(repair_retries + 1):
            raw = self.chat(system, prompt, images=images)
            try:
                s = raw[raw.index("{"):raw.rindex("}") + 1]
                obj = json.loads(s)
            except Exception:
                prompt = (user + "\n\nYour previous reply was not valid "
                          "JSON. Respond with ONE JSON object only.")
                continue
            errs = validate(obj) if validate else []
            if not errs:
                return obj
            prompt = (user + "\n\nYour previous JSON had problems: "
                      + "; ".join(str(e) for e in errs[:4])
                      + ". Fix them and respond with ONE JSON object.")
        raise RuntimeError("relay answers failed validation after retries")

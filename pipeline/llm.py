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


def make_client(temperature=0.1, max_output_tokens=14000):
    """The run engine from the environment (LLM_BASE_URL / LLM_API_KEY /
    LLM_MODEL) — pure gpt-5.6-luna in dispatched runs per the standing
    directive; the env decides, code does not."""
    return Client(temperature=temperature, max_output_tokens=max_output_tokens)


def env_ready():
    return all(os.environ.get(k) for k in
               ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))

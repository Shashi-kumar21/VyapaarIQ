"""Claude client (T2.1).

* Key: ``ANTHROPIC_API_KEY`` (or any credential the SDK resolves).
* Model: ``LLM_MODEL`` env var, default ``claude-opus-5-5``.
* Effort: ``LLM_EFFORT`` env var (low|medium|high), default ``medium``.
* 60 s timeout, one SDK retry; server-side refusal fallback enabled.
* Returns parsed JSON only; strips ```json fences; never logs document text.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMUnavailable(RuntimeError):
    """No credentials / SDK, or the model refused."""


class LLMBadJSON(ValueError):
    """The model did not return parseable JSON."""


def llm_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def model_name() -> str:
    return os.environ.get("LLM_MODEL") or DEFAULT_MODEL


def parse_json(text: str) -> Any:
    """Parse a JSON object from model output, tolerating code fences / prose around it."""
    t = _FENCE.sub("", text.strip())
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(t[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMBadJSON("Model output was not valid JSON.")


class ClaudeClient:
    def __init__(self, client: Optional[Any] = None):
        if client is not None:
            self._client = client
            return
        if not llm_configured():
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable("anthropic SDK not installed.") from exc
        self._client = anthropic.Anthropic(timeout=60.0, max_retries=1)

    def complete_json(self, system: str, content: list[dict], max_tokens: int = 8000) -> Any:
        import anthropic

        try:
            resp = self._client.beta.messages.create(
                model=model_name(),
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": os.environ.get("LLM_EFFORT", "medium")},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailable("Could not reach the Claude API.") from exc
        except anthropic.APIStatusError as exc:
            log.warning("Claude API error status=%s request_id=%s", exc.status_code,
                        getattr(exc, "request_id", None))
            raise LLMUnavailable(f"Claude API error {exc.status_code}.") from exc

        if resp.stop_reason == "refusal":
            raise LLMUnavailable("Model declined the request.")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        log.info("Claude call ok model=%s request_id=%s", resp.model, getattr(resp, "_request_id", None))
        return parse_json(text)

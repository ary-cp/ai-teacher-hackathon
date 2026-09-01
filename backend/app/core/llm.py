"""Thin, defensive wrapper around Groq (Llama-3.x) via LangChain.

Two things matter for a live demo:
  * JSON must never break the state machine  -> `json_call` repairs + retries.
  * Latency must stay low                    -> small model for routing/eval,
                                                big model for teaching.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.config import settings

log = logging.getLogger("ai-teacher.llm")

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _client(model: str, temperature: float, json_mode: bool) -> ChatGroq:
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model,
        temperature=temperature,
        max_tokens=2048,
        timeout=60,
        max_retries=2,
        model_kwargs=kwargs,
    )


def chat(
    prompt: str,
    *,
    system: str = "",
    fast: bool = False,
    temperature: float = 0.4,
) -> str:
    """Plain text completion."""
    model = settings.groq_model_fast if fast else settings.groq_model_teach
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    return _client(model, temperature, json_mode=False).invoke(messages).content


def _extract_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    fence = _FENCE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # last resort: grab the outermost {...}
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidate = raw[start : end + 1]
        # strip trailing commas, a classic Llama slip
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        return json.loads(candidate)
    raise ValueError("no JSON object found in model output")


def json_call(
    prompt: str,
    *,
    system: str = "You reply with a single valid JSON object and nothing else.",
    fast: bool = False,
    temperature: float = 0.3,
    retries: int = 2,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured completion that is safe to feed straight into the state machine."""
    model = settings.groq_model_fast if fast else settings.groq_model_teach
    last_err: Exception | None = None

    for attempt in range(retries + 1):
        try:
            msgs = [SystemMessage(content=system), HumanMessage(content=prompt)]
            if attempt:
                msgs.append(
                    HumanMessage(
                        content="Your previous reply was not valid JSON. "
                        "Reply again with ONLY the JSON object."
                    )
                )
            raw = _client(model, temperature, json_mode=True).invoke(msgs).content
            return _extract_json(raw)
        except Exception as exc:  # noqa: BLE001 - demo resilience beats purity
            last_err = exc
            log.warning("json_call attempt %s failed: %s", attempt + 1, exc)

    if fallback is not None:
        log.error("json_call exhausted retries, using fallback: %s", last_err)
        return fallback
    raise RuntimeError(f"LLM JSON call failed: {last_err}")

"""One way to ask an LLM for structured output, shared by the rule compiler (docs/06) and
verification (docs/09).

``generate(Schema, system=..., parts=[...], purpose="compile")`` returns the answer parsed
into ``Schema`` (a Pydantic model), with token counts and timing for the usage ledger.

Providers (LLM_PROVIDER):
- ``gemini``: several free-tier keys and models are tried in order. A key/model that hits a
  daily quota rests for an hour; a per-minute limit only for a moment.
- ``fake``: tests and offline demos. Answers come from functions registered per purpose with
  ``fake_answers.register(purpose, fn)``; nothing leaves the machine.
"""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
COOLDOWN_S = 3600  # after a daily-quota error
RETRY_WAIT_S = 15  # after a per-minute limit or an overloaded model
ROUNDS = 3
_exhausted: dict[tuple[int, str], float] = {}  # (key index, model) -> retry after


class LlmError(Exception):
    """The model couldn't answer. ``str(exc)`` is safe to show to a user."""


@dataclass(frozen=True)
class Image:
    data: bytes
    mime_type: str = "image/jpeg"


Part = str | Image


@dataclass
class LlmResult[T: BaseModel]:
    data: T
    provider: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


def generate[T: BaseModel](
    schema: type[T], *, system: str, parts: Sequence[Part], purpose: str
) -> LlmResult[T]:
    provider = settings.LLM_PROVIDER
    if provider == "gemini":
        return _gemini(schema, system, parts)
    if provider == "fake":
        return fake_answers.answer(schema, system, parts, purpose)
    raise LlmError(f"Unknown LLM_PROVIDER {provider!r}")


# --- fake ---


FakeFn = Callable[[str, Sequence[Part]], dict[str, Any]]


class _FakeAnswers:
    def __init__(self) -> None:
        self._fns: dict[str, FakeFn] = {}

    def register(self, purpose: str, fn: FakeFn) -> None:
        self._fns[purpose] = fn

    def clear(self) -> None:
        self._fns.clear()

    def answer[T: BaseModel](
        self, schema: type[T], system: str, parts: Sequence[Part], purpose: str
    ) -> LlmResult[T]:
        fn = self._fns.get(purpose)
        if fn is None:
            raise LlmError(f"The offline AI has no answers for {purpose!r}.")
        try:
            data = schema.model_validate(fn(system, parts))
        except ValidationError as exc:
            raise LlmError("The AI's answer didn't match the schema.") from exc
        return LlmResult(data, "fake", "fake")


fake_answers = _FakeAnswers()


# --- gemini ---


def _gemini[T: BaseModel](schema: type[T], system: str, parts: Sequence[Part]) -> LlmResult[T]:
    from google import genai
    from google.genai import errors, types

    if not settings.GEMINI_API_KEYS:
        raise LlmError("No Gemini API key is configured.")
    contents: list[Any] = [
        types.Part.from_bytes(data=p.data, mime_type=p.mime_type) if isinstance(p, Image) else p
        for p in parts
    ]
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0,
    )
    last_error = "every key and model is over its limit; try again later"
    for attempt in range(ROUNDS):
        if attempt:
            time.sleep(RETRY_WAIT_S)  # per-minute limits reset quickly
        busy = False
        for model in settings.GEMINI_MODELS:
            for index, key in enumerate(settings.GEMINI_API_KEYS):
                if _exhausted.get((index, model), 0) > time.time():
                    continue
                started = time.monotonic()
                client = genai.Client(api_key=key)  # keep a reference: it closes when collected
                try:
                    response = client.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                except errors.APIError as exc:
                    if exc.code in (429, 403):
                        daily = exc.code == 403 or "day" in str(exc).lower()
                        _exhausted[(index, model)] = time.time() + (
                            COOLDOWN_S if daily else RETRY_WAIT_S
                        )
                        busy = busy or not daily
                        log.warning("Gemini key %d on %s: %s", index + 1, model, exc.code)
                        continue
                    if exc.code in (500, 503, 504):  # overloaded model: try the next one
                        last_error, busy = f"{model} is overloaded", True
                        break
                    log.warning("Gemini %s: %s", exc.code, str(exc)[:300])
                    raise LlmError(f"Gemini error {exc.code}") from exc
                parsed = response.parsed
                if not isinstance(parsed, schema):
                    try:
                        parsed = schema.model_validate_json(response.text or "")
                    except ValidationError as exc:
                        raise LlmError("The AI's answer didn't match the schema.") from exc
                usage = response.usage_metadata
                return LlmResult(
                    parsed,
                    "gemini",
                    model,
                    input_tokens=(usage.prompt_token_count or 0) if usage else 0,
                    output_tokens=(usage.candidates_token_count or 0) if usage else 0,
                    ms=int((time.monotonic() - started) * 1000),
                    meta={"key": index + 1},
                )
        if not busy:
            break  # only daily limits left: waiting won't help
    raise LlmError(f"Gemini unavailable: {last_error}.")

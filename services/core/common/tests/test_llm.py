import pytest
from pydantic import BaseModel

from common.llm import Image, LlmError, fake_answers, generate


class Verdict(BaseModel):
    answer: str
    confidence: float


@pytest.fixture(autouse=True)
def _fake(settings):
    settings.LLM_PROVIDER = "fake"
    yield
    fake_answers.clear()


def test_fake_answers_are_parsed_into_the_schema() -> None:
    seen = {}

    def answer(system, parts):
        seen["parts"] = parts
        return {"answer": "no", "confidence": 0.91}

    fake_answers.register("verify", answer)
    result = generate(
        Verdict, system="Answer yes or no.", parts=["Helmet?", Image(b"jpeg")], purpose="verify"
    )
    assert result.data == Verdict(answer="no", confidence=0.91)
    assert result.provider == "fake"
    assert seen["parts"][1] == Image(b"jpeg", "image/jpeg")


def test_unknown_purpose_and_bad_answers_are_errors() -> None:
    with pytest.raises(LlmError, match="no answers"):
        generate(Verdict, system="", parts=[], purpose="compile")
    fake_answers.register("compile", lambda system, parts: {"answer": "yes"})
    with pytest.raises(LlmError, match="schema"):
        generate(Verdict, system="", parts=[], purpose="compile")


def test_gemini_needs_a_key(settings) -> None:
    settings.LLM_PROVIDER = "gemini"
    settings.GEMINI_API_KEYS = []
    with pytest.raises(LlmError, match="No Gemini API key"):
        generate(Verdict, system="", parts=[], purpose="verify")


def test_unknown_provider(settings) -> None:
    settings.LLM_PROVIDER = "carrier-pigeon"
    with pytest.raises(LlmError, match="Unknown LLM_PROVIDER"):
        generate(Verdict, system="", parts=[], purpose="verify")

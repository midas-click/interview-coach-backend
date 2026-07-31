"""Prompt store tests."""

import pytest

from services.prompts import PromptStore


@pytest.fixture
def store() -> PromptStore:
    return PromptStore()


def test_loads_all_prompts(store: PromptStore) -> None:
    names = store.names()
    assert {
        "conversation_parser",
        "interview_coach",
        "english_coach",
        "vocabulary",
        "recommendation",
    }.issubset(set(names))


def test_frontmatter_metadata(store: PromptStore) -> None:
    t = store.get("interview_coach")
    assert t.version
    assert t.purpose
    assert "transcript" in t.variables
    assert t.body.startswith("#")


def test_render_validates_variables(store: PromptStore) -> None:
    rendered = store.render("interview_coach", interview_id="1", transcript="hi", qa_pairs="[]")
    assert "1" in rendered
    assert "hi" in rendered


def test_render_rejects_undeclared_variable(store: PromptStore) -> None:
    with pytest.raises(ValueError, match="undeclared"):
        store.render("interview_coach", nope="x")


def test_render_rejects_missing_variable(store: PromptStore) -> None:
    with pytest.raises(ValueError, match="missing"):
        store.render("interview_coach", transcript="hi")


def test_unknown_prompt_raises(store: PromptStore) -> None:
    with pytest.raises(KeyError):
        store.render("does_not_exist")

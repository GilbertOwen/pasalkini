import httpx

from pasalkini.evals import runner
from pasalkini.evals.schema import load_golden
from pasalkini.pipelines import CONFIGS


def test_failed_generation_is_retried_once_then_recorded(monkeypatch):
    calls = []

    def hangs(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(runner, "generate", hangs)
    item = load_golden()[0]
    result = runner.evaluate_item(item, CONFIGS["temporal"], lambda allowed: [], False)
    assert len(calls) == 2
    assert result.answer.startswith("ERROR: ReadTimeout") and not result.json_ok


def test_a_forced_misreading_changes_only_the_kind_of_question():
    from pasalkini.answer.llm import Reply
    from pasalkini.answer.understand import Classification
    from pasalkini.answer.verify import Selection
    from pasalkini.evals.misread import forced, ordinary_questions

    def model(options, messages, schema):
        parsed = schema(kutipan=[])
        return Reply(parsed, "from the model", 1, 1, 0.0)

    chat = forced("status", model)
    assert chat(None, [], Classification).parsed.intent == "status"
    assert chat(None, [], Selection).raw == "from the model"
    # Only development questions that ask what the law says, from both sets.
    items = ordinary_questions()
    assert items and all(item.split == "dev" and not item.should_abstain for item in items)
    assert {"status", "what_changed", "calculation"}.isdisjoint(i.category.value for i in items)
    assert any(item.id.endswith("-v") for item in items)

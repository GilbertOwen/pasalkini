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

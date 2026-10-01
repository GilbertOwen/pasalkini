"""The HTTP API over the service, with the scripted model of test_service."""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_answer_pipeline import FOUR, OLD, PICKS_OLD, SAID, THREE, ScriptedChat
from test_service import make_service

from pasalkini.api.main import create_app


@pytest.fixture
def client(tmp_path) -> TestClient:
    service = make_service(tmp_path, ScriptedChat(selections=[PICKS_OLD, PICKS_OLD]))
    return TestClient(create_app(service, ui=False))


def events_of(text: str) -> list[tuple[str, dict]]:
    """Server-sent events as (event, data) pairs."""
    found = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        found.append((fields["event"], json.loads(fields["data"])))
    return found


def test_a_question_is_answered_in_one_response(client):
    response = client.post(
        "/ask/json", json={"question": "Berapa jam lembur maksimal?", "date": "2019-06-01"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == SAID and body["as_of"] == "2019-06-01"
    assert [c["source_id"] for c in body["citations"]] == [OLD.source_id]


def test_a_question_is_answered_as_a_stream_of_stages_and_then_the_answer(client):
    response = client.post(
        "/ask", json={"question": "Berapa jam lembur maksimal?", "date": "2019-06-01"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = events_of(response.text)
    assert [kind for kind, _ in events] == ["stage", "stage", "stage", "stage", "answer"]
    assert events[0][1] == {"stage": "understand", "label": "Memahami pertanyaan"}
    assert events[-1][1]["answer"] == SAID


def test_a_question_without_a_date_is_about_today(client):
    body = client.post("/ask/json", json={"question": "Berapa jam lembur maksimal?"}).json()
    assert body["as_of"] == "2026-10-01" and body["as_of_source"] == "today"


def test_a_bad_request_is_refused_with_the_reason(client):
    assert client.post("/ask/json", json={"question": ""}).status_code == 422
    assert client.post("/ask/json", json={"question": "   "}).status_code == 422
    assert client.post("/ask/json", json={"question": "x" * 2001}).status_code == 422
    wrong_date = client.post("/ask/json", json={"question": "Lembur?", "date": "kemarin"})
    assert wrong_date.status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_a_model_server_that_is_down_is_a_503(tmp_path):
    def down(options, messages, schema):
        raise ConnectionError("Failed to connect to Ollama")

    client = TestClient(create_app(make_service(tmp_path, down), ui=False))
    response = client.post("/ask/json", json={"question": "Berapa jam lembur maksimal?"})
    assert response.status_code == 503 and "Ollama" in response.json()["detail"]
    assert response.headers["retry-after"] == "30"
    stream = client.post("/ask", json={"question": "Berapa jam lembur maksimal?"})
    kind, data = events_of(stream.text)[-1]
    assert kind == "error" and data["status"] == 503
    # What does not need the model still works.
    assert client.get("/provisions/uu-13-2003/pasal-78?as_of=2019-06-01").status_code == 200


def test_an_article_is_served_as_it_stood_on_the_date(client):
    old = client.get("/provisions/uu-13-2003/pasal-78", params={"as_of": "2019-06-01"}).json()
    assert old["text"] == THREE and old["source_id"] == OLD.source_id
    now = client.get("/provisions/uu-13-2003/pasal-78").json()  # today
    assert now["text"] == FOUR and now["as_of"] == "2026-10-01" and now["status"] == "conditional"


def test_an_article_that_is_unknown_or_not_yet_in_force_is_a_404(client):
    unknown = client.get("/provisions/uu-13-2003/pasal-999")
    assert unknown.status_code == 404 and "tidak ada" in unknown.json()["detail"]
    early = client.get("/provisions/pp-35-2021/pasal-16", params={"as_of": "2019-06-01"})
    assert early.status_code == 404 and "belum berlaku pada 1 Juni 2019" in early.json()["detail"]
    assert client.get("/provisions/uu-13-2003/pasal-78?as_of=2019-13-45").status_code == 422


def test_an_articles_history_is_served_with_its_changes(client):
    response = client.get("/provisions/uu-13-2003/pasal-78/history")
    assert response.status_code == 200
    versions = response.json()["versions"]
    assert [v["status"] for v in versions] == ["in_force", "in_force", "conditional"]
    assert ["lama 4 (empat)", "+"] in versions[1]["diff"]
    assert client.get("/provisions/uu-13-2003/pasal-999/history").status_code == 404


def test_a_law_is_served_as_it_stood_on_the_date(client):
    listed = client.get("/laws").json()
    assert [law["id"] for law in listed] == ["uu-13-2003", "pp-35-2021"]
    law = client.get("/laws/uu-13-2003", params={"as_of": "2019-06-01"}).json()
    assert [a["label"] for a in law["articles"]] == ["Pasal 78", "Pasal 79"]
    one = client.get("/laws/uu-13-2003", params={"as_of": "2021-01-01", "pasal": ["78"]}).json()
    assert [a["text"] for a in one["articles"]] == [FOUR]
    assert client.get("/laws/uu-99-1999").status_code == 404


def test_severance_is_computed_by_rule(client):
    reasons = client.get("/calc/pesangon/reasons", params={"date": "2024-03-01"}).json()
    assert reasons and all(isinstance(text, str) for text in reasons.values())
    body = {
        "tanggal_mulai": "2018-03-01",
        "tanggal_phk": "2024-03-01",
        "upah_bulanan": 5_000_000,
        "alasan": next(iter(reasons)),
    }
    result = client.post("/calc/pesangon", json=body).json()
    assert result["service"] == "6 tahun 0 bulan" and result["total"] > 0
    assert result["lines"][0]["basis"] and result["as_of"] == "2024-03-01"
    unknown = client.post("/calc/pesangon", json={**body, "alasan": "tidak-ada"})
    assert unknown.status_code == 422 and "tidak dikenal" in unknown.json()["detail"]
    assert client.post("/calc/pesangon", json={**body, "upah_bulanan": -1}).status_code == 422
    backwards = {**body, "tanggal_mulai": "2025-01-01"}
    assert client.post("/calc/pesangon", json=backwards).status_code == 422


def test_contract_compensation_is_computed_by_rule(client):
    contract = {"tanggal_mulai": "2022-01-01", "tanggal_berakhir": "2023-07-01"}
    body = {**contract, "upah_bulanan": 6_000_000}
    result = client.post("/calc/kompensasi-pkwt", json=body).json()
    assert result["total"] == 9_000_000 and result["regime"] == "pp-35-2021"


def test_health_reports_the_corpus_and_the_model_server(client, monkeypatch):
    import ollama

    class Down:
        def __init__(self, timeout):
            pass

        def list(self):
            raise ConnectionError("down")

    monkeypatch.setattr(ollama, "Client", Down)
    health = client.get("/health")
    assert health.status_code == 200  # the app itself is up
    assert health.json()["status"] == "degraded" and health.json()["corpus"]["chunks"] == 5


def test_the_api_describes_itself(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/ask", "/ask/json", "/health", "/laws", "/calc/pesangon"} <= set(paths)
    assert date.today().year >= 2026  # a reminder that 'today' is the service's, not the test's

# Architecture

PasalKini answers a labor-law question with the law that applied on a given date. This page shows how the pieces fit; `PLAN.md` explains why the project exists and what comes next.

## Data flow

```
OFFLINE (when a legal instrument is added or changes)

sources/manifest.yaml ──► download ──► extract ──► parse ──────────────► data/processed/<id>.json
  (official URLs,          (robots.txt,  (PyMuPDF,    (numbering-order      articles, ayat, amendment
   dates, parse hints)      3 s apart,    headers,     state machine,       points, MK rulings,
                            SHA-256)      stamps)      OCR repair)          penjelasan, closing
                                                                                  │
sources/events-manual.yaml ───────────────────────────────┐                      ▼
                                                           ├──► extract events ──► replay by date ──► data/processed/pasalkini.db
sources/events-review.csv (human verdicts) ───────────────┘    (enact, amend,      (versions with      (event, version)
                                                                insert, delete,     valid_from/to and
                                                                interpret, revoke)  status)

ONLINE (per question, answer/pipeline.py)

question (+ date) ─► date: read from the question, else the date picker, else today          rules
                 ─► kind: explain | status | history | calculate | out of scope             qwen3.5:4b, JSON
                 ─► out of scope ─► refusal and referral (no search)
                 ─► a calculation, or a dismissal whose payments are asked about
                    ─► the model reads the facts; tools/pesangon.py computes                 code
                 ─► context: articles the question names, the severance tables for a
                    severance question, the calculator's articles, then dense + BM25
                    search over the versions that applied on the date
                    (every version up to it for status and history questions)
                 ─► status of a named article ─► answered from the temporal model            code
                 ─► an amount that was asked for ─► answered from the calculator             code
                 ─► otherwise:
                    1. the model picks quotes from the context                               qwen3.5:4b, JSON
                    2. code finds each quote (near matches allowed, never a different        code
                       number) in a text that applied on the date; one repair
                    3. code lays out the passages: the quoted lines, the line that opens
                       their ayat, lines that refer back to them, and what the
                       Constitutional Court ruled about them
                    4. the model answers from the passages alone: first the words it         qwen3.5:4b, JSON
                       answers from, then any limit on them, then the answer
                       (a question about change: one summary of the old wording, one of
                       the current)
                    5. code checks the answer's numbers, articles and dates against          code
                       what it was given; one rewrite
                 ─► no answer in the passages ─► the model picks again, once
                 ─► still none ─► articles that began after the date are searched:
                    "not yet in force on that date", or abstain and show what was found
                 ─► notes by code: rulings on the cited articles, what changed after the date
```

## The app

```
browser ─► /ui  (ui/app.py, Gradio: Tanya, Riwayat Pasal, Konsolidasi, Kalkulator) ─┐
client  ─► API  (api/main.py, FastAPI: /ask as server-sent events, /provisions,      ├─► service.py
                 /laws, /calc, /health) ───────────────────────────────────────────┘

Service.ask(question, date)
  ─► redact: NIK, NPWP, phone, e-mail, cued names ─► placeholders                    code
  ─► cache: same question, date, corpus, law state, settings and code? ─► answer     SQLite
  ─► one question at a time (one GPU)
  ─► embed the question on the CPU, then the pipeline above; each stage is a span
     that is told to the waiting user and, if asked for, sent to Phoenix
  ─► model server down ─► "model unavailable" (HTTP 503), not a crash
  ─► store in the cache (unless personal data was found or a reply was cut short)
  ─► log one line: redacted question, date, kind, sources, timings; no answer text

Service.provision / history / law / severance / pkwt_compensation
  ─► the temporal model and the calculator's rules; no model call
```

`uv run pasalkini serve` runs all of it in one process on 127.0.0.1.

## Key ideas

| Idea | Where | Why |
|---|---|---|
| Source IDs say where wording was published (`perppu-2-2022/pasal-81/angka-15`) | everywhere | Evaluation labels written before the temporal model existed stay valid after it |
| Parse by numbering order | `ingest/parse.py` | OCR breaks markers; knowing what comes next repairs `(21` → (2), `Pasal 8O` → 80, `L7.` → 17 |
| Events are the source of truth | `temporal/events.py`, `temporal/build.py` | A new law is more events, not hand edits; versions can always be rebuilt |
| Three statuses: in force, conditional, repealed | `temporal/model.py` | MK conditional rulings and "sepanjang tidak bertentangan" clauses are real legal states |
| Revocation restores replaced wording | `temporal/build.py` | Perppu 2/2022 revoked UU 11/2020 (Pasal 185) while restating its amendments |
| Filter by date before ranking | `retrieve/temporal.py` | A version that did not apply cannot be retrieved, so it cannot be cited |
| Arithmetic in code | `tools/pesangon.py` | Exact, testable, and each rule names its article |
| Code checks every quote | `answer/verify.py` | A small model tidies what it copies and mixes up IDs; the check finds the passage, refuses a changed number, and shows the source's own words |
| Pick the passages first, then answer from them alone | `answer/pipeline.py` | Answering over seven articles at once, the model mixed details between them and misread long ones. Correct answers on the development questions went from 23 to 33-36 of 42 |
| What code can state, the model does not write | `answer/context.py`, `tools/pesangon.py`, `temporal/rulings.py` | An article's status, a severance amount and the effect of a court ruling come from the temporal model, the rules and the ruling's fixed formula. The model's own versions of these were where the mistakes were |
| The answer's sentences are checked too | `answer/verify.py: ungrounded` | Every number and article the answer mentions must be in what it was given; after an opening by code, sentences that fail are left out |
| A fixed pipeline, not an agent | `answer/pipeline.py`, `answer/agent.py` | Measured: letting the 4B model choose its own searches and tools cites an expected source in 81% of answers against 91%, and is slower (`docs/eval-results.md`) |
| One service behind the API and the screens | `service.py` | The rules of the app (redaction, cache, one question at a time, a clear error when the model is down) are written and tested once |
| Personal data goes out on the way in | `privacy/redact.py` | Nothing downstream can keep what it never saw. It is also noise to the search: a name and a phone number in front of a question retrieved the wrong article |
| A cache key made of what an answer is made from | `cache.py` | Question, date, corpus fingerprint, the last day the law changed, model settings, and a fingerprint of the code: a stale answer cannot be served after a new law, a new prompt or a new check |
| Stages as spans | `trace.py` | The same record tells a waiting user what is happening and, on request, shows a question's whole path in Phoenix. Outside the app it does nothing |
| Legal text is never passed through Markdown | `ui/render.py` | A line starting "3." would be renumbered as a list item. Text is escaped and keeps its own line breaks |
| A retrieval gate that needs no model | `evals/gate.py` | CI has no GPU. A snapshot of the corpus and question embeddings in git lets every push be checked for Recall@5 and for outdated text in the top 5 |

## Checks that keep it honest

- Parser: UU 13/2003 parses to exactly 193 articles; Pasal 81 points are continuous in both Cipta Kerja texts; MK 168's citations of Perppu point numbers match where the parser placed each article.
- Temporal model: property tests (a new event never changes the law before its date; versions never overlap or leave gaps) and fact tests against the primary texts.
- Answers: the pipeline is tested end to end with a scripted model (every path: picked, repaired, rewritten, picked again, abstained, refused, status and amount by code, old and current wording, later law).
- Evaluation: every label must match a chunk in the corpus; runs record the config, git commit, model digests and dataset fingerprint, and start from a freshly loaded model; `rescore` re-scores a run when keys change.
- Correctness: answers are graded by reading (`grades-*.csv`), and the automatic judge is used only as far as it agrees with that reading (`pasalkini agreement`).
- App: the service, the API and what the screens show are tested with the scripted model (cache hits, personal data never reaching the model or the log, a model server that is down, every endpoint). Redaction is tested to leave every evaluation question unchanged, so the evaluation numbers hold for the app's path. The screens were also tried by hand in a browser.
- CI: lint, the tests, and the retrieval gate on every push (`.github/workflows/ci.yml`).

## Storage

| What | Where | In git |
|---|---|---|
| Official PDFs | `data/raw/` | no (re-download with `pasalkini download`) |
| Parsed documents | `data/processed/<id>.json` | no |
| Events and versions | `data/processed/pasalkini.db` | no |
| Embedding cache | `data/processed/index/` | no |
| Source list, manual events, review sheet | `sources/` | yes |
| Evaluation runs | `evals/runs/<run>/` | summary, config, grading sheet, grades by reading, the judge's grades (not the answers themselves) |
| Retrieval snapshot for CI | `evals/fixtures/retrieval.npz` | yes (1.8 MB; remade with `pasalkini fixture`) |
| Question log | `data/logs/<day>.jsonl` | no (redacted; deleted after 30 days) |
| Answer cache | `data/cache/answers.db` | no (keys are hashes; no question text) |

# PasalKini: Build Plan

Date-aware legal information assistant for Indonesian labor law.
Plan v1, 30 September 2026. Companion to [PasalKini: Project Brief and Legal Review](https://docs.google.com/document/d/1K8jFcSevIa8nTQAQv3emnZQDBh0L_d-MJR_yHxkwDcM/edit).

> PasalKini gives legal information, not legal advice. Every design choice below assumes that.

---

## 1. What we're building

Ask a labor-law question and a date. Get the answer that was legally correct on that date, citing the exact version of each article, with a warning if the rule has changed since.

### Features (v1)

| Screen | What it does |
|---|---|
| **Tanya** (Ask) | Question + optional date (defaults to today) → plain-Indonesian answer, cited article versions, confidence, a "this rule changed on …" note, and a referral when needed |
| **Riwayat Pasal** (Article history) | Timeline of one article across laws, regulations and MK decisions, with a word-level diff between any two versions |
| **Konsolidasi** (Law as of a date) | Full text of a law as it stood on any date |
| **Kalkulator Pesangon** (Severance) | Deterministic calculation under the rules in force on the dismissal date, with the legal basis for each line |

### Scope (v1)

- **Instruments (core chain, about 10):** UU 13/2003 · UU 11/2020, Perppu 2/2022 and UU 6/2023 (Bab IV Ketenagakerjaan only) · MK 168/PUU-XXI/2023 · PP 35/2021 · PP 36/2021 and PP 51/2023 (wages) · the new labor law once it is promulgated.
- **Topics (about 9):** PKWT · PKWTT and probation · outsourcing (alih daya) · working hours and overtime · rest and leave · wages and minimum wage · dismissal procedure (PHK) · severance (pesangon, UPMK, UPH) · platform workers (if the new law covers them).

### Not in v1

Other areas of law · provincial and district minimum wage amounts (UMP/UMK decrees) · court decisions other than MK · drafting documents · advice on a specific case · public hosting (see Phase 8).

### Assumptions

- About **20 hours a week → about 13 weeks**. Full-time: about 6–7 weeks. If you start this week, v1 lands around the end of December 2026.
- Your machine: RTX 3060 Laptop GPU (6 GB VRAM), 16 GB RAM, Windows 11. Everything in v1 runs locally.
- Installed: Python 3.10.6 (the project uses a uv-managed Python 3.12), uv 0.11, Git, Ollama with `qwen3.5:4b` and `qwen3-embedding:0.6b`. **Not installed:** Docker (needed in Phase 7).

---

## 2. Timeline

| Phase | Focus | Weeks | You'll have at the end |
|---|---|---|---|
| 0 | Setup, scope, seed evaluation | 1 | Repo, source manifest, 20 dated test questions |
| 1 | Data pipeline | 2 | Every core instrument parsed to article level, with tests |
| 2 | Baseline RAG + evaluation harness | 1 | A number: how often plain RAG cites law that wasn't in force |
| 3 | **Temporal model** (the core) | 2 | Any article at any date, change history, diffs |
| 4 | Retrieval quality | 1 | Hybrid search + reranker, ablation table |
| 5 | Answer pipeline, tools, guardrails | 2 | Working CLI assistant with verified citations and the calculator |
| 6 | Full evaluation | 1 | 150-question results, model comparison, error analysis |
| 7 | Application and operations | 2 | FastAPI + Gradio app, privacy, tracing, Docker, CI |
| 8 | Portfolio launch | 1 | README, public benchmark, demo video, write-up |
| 9 | Stretch: fine-tuning | 1–2 | Small fine-tuned model vs prompting, measured |

Worth posting about publicly: end of Phase 2 (the problem, measured), Phase 3 (what the new law changed, article by article), Phase 6 (results), Phase 8 (launch).

### The new labor law runs alongside the plan

The DPR has targeted **8 October 2026** for passing the RUU Pelindungan Ketenagakerjaan; the MK deadline is 31 October 2026. PKWT duration and outsourcing were still contested in late September, and reports differ on whether it is a standalone law or a revision of UU 13/2003.

- **Never build on drafts.** Use only the promulgated text (with a law number) from peraturan.go.id or JDIH. A bill approved jointly by the DPR and the government becomes law within 30 days even without the President's signature (UUD 1945 Pasal 20 ayat 5), so expect the official text within about a month of passage.
- Record three dates: approved by the DPR, promulgated, in force. Also record articles with later start dates and the transitional provisions.
- The data model (Phase 3) handles both outcomes: a revision becomes more amendment events; a replacement law gets an article lineage map (old article → new article).
- When the official text arrives: Phase 1 pipeline → Phase 3 events → new-law questions in the eval set. If it arrives after Phase 3, use the update runbook from Phase 7.
- Expect challenges at the MK after passage. They are just more events.

---

## 3. Architecture

```
OFFLINE: run whenever a legal instrument is added or changes

 sources/manifest.yaml
        |
        v
 [download] --> [extract text] --> [parse structure] --> [extract change events] --> events table
  polite,         PyMuPDF,           BAB/Pasal/ayat,       regex first, LLM for          |
  logged          clean-up           tested                the rest, human review        v
                                                                                 [build versions]
                                                                                 replay events by date
                                                                                         |
                                                                                         v
                                       indexes (BM25 + embeddings) <--  SQLite temporal store

ONLINE: per question

 question (+ date) --> [understand] --> [retrieve: filter to as-of date, then rank] --> [rerank] --> [generate JSON]
                       as-of date,       hybrid BM25 + dense                                             |
                       topic, intent                                                                     v
                           |                                                                     [verify citations]
                           +-- calculate --> [pesangon calculator] ---------------------------> in force? quote exact?
                                                                                                         |
                                                              answer + citations + "changed since" note, or a refusal
```

### Design principles

1. **The unit of knowledge is an article version**, not an arbitrary chunk. Each version has `valid_from` / `valid_to`, and every answer cites a version.
2. **Events are the source of truth; versions are rebuilt from them** (event sourcing). Adding a new law means adding events and rebuilding, never editing versions by hand.
3. **Validity has three states:** in force, not in force, or *conditional*: an MK conditional ruling, or an old regulation kept "sepanjang tidak bertentangan" (as long as it doesn't conflict) with a new law. Conditional means a caveat and lower confidence.
4. **Filter by date before ranking**, so a version that wasn't in force can never be retrieved.
5. **Code does the maths.** The calculator is deterministic; the LLM explains the result.
6. **Code checks every citation** before the user sees it.
7. **Pipeline first, agent second.** A 4B model is more reliable in a fixed flow; the agent loop is added for multi-step questions and has to beat the pipeline on the evals.

---

## 4. Data model

Every piece of legal text gets a **source ID** that says where it was published: `uu-13-2003/pasal-59` is the original Pasal 59, and `perppu-2-2022/pasal-81/angka-N` is the new wording of Pasal 59 published in the Perppu. Source IDs exist from Phase 1, before the temporal model, so evaluation labels written in Phase 0 stay valid for the whole project.

```sql
-- Laws, regulations and MK decisions
CREATE TABLE instrument (
  id              TEXT PRIMARY KEY,   -- 'uu-13-2003', 'perppu-2-2022', 'mk-168-puu-xxi-2023'
  kind            TEXT NOT NULL,      -- UU | PERPPU | PP | PERMEN | PUTUSAN_MK
  number TEXT, year INTEGER, title TEXT,
  approved_on     DATE,               -- joint DPR approval (UU only)
  promulgated_on  DATE,               -- diundangkan, or pronounced (MK)
  in_force_on     DATE,               -- mulai berlaku
  source_url TEXT, sha256 TEXT, retrieved_at TEXT
);

-- Stable identity of an article across time
CREATE TABLE provision (
  id            TEXT PRIMARY KEY,     -- 'uu-13-2003/pasal-59'
  instrument_id TEXT NOT NULL REFERENCES instrument(id),
  label         TEXT NOT NULL         -- 'Pasal 59'
);

-- Every change, from any source. This is the source of truth.
CREATE TABLE event (
  id                   TEXT PRIMARY KEY,
  source_id            TEXT NOT NULL, -- where the change was published: 'perppu-2-2022/pasal-81/angka-N'
  op                   TEXT NOT NULL, -- enact | amend | insert | delete | revoke | reenact | mk_conditional | mk_annul
  target_provision_id  TEXT REFERENCES provision(id),
  effective_on         DATE NOT NULL,
  new_text             TEXT,          -- for enact / amend / insert
  note                 TEXT,          -- MK ruling wording, transitional clause
  review               TEXT NOT NULL DEFAULT 'pending'  -- pending | verified | rejected
);

-- Derived from events by build_versions.py. Never edited by hand.
CREATE TABLE version (
  id               TEXT PRIMARY KEY,  -- 'uu-13-2003/pasal-59/v2'
  provision_id     TEXT NOT NULL REFERENCES provision(id),
  source_id        TEXT NOT NULL,     -- where this wording was published
  text             TEXT NOT NULL,
  valid_from       DATE NOT NULL,
  valid_to         DATE,              -- NULL = still applies
  status           TEXT NOT NULL,     -- in_force | conditional | not_in_force
  text_changed     INTEGER NOT NULL,  -- 0 when re-enacted with identical wording
  created_by_event TEXT REFERENCES event(id)
);

-- When a new law replaces an old one: which article became which
CREATE TABLE lineage (
  old_provision_id TEXT, new_provision_id TEXT,
  relation TEXT,                      -- same | split | merged | partial
  verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE provision_topic (provision_id TEXT, topic TEXT);
```

Retrieval chunks (one per version, or one per ayat) keep `version_id`, `valid_from`, `valid_to` and a header such as `UU 13/2003 · Pasal 59 · PKWT`. Their embeddings live in a NumPy array aligned by row.

### Answer contract

```json
{
  "as_of": "2021-03-15",
  "as_of_source": "question | date_picker | today",
  "intent": "explain | status | history | calculate | out_of_scope",
  "answer": "Plain-Indonesian explanation …",
  "citations": [{"version_id": "uu-13-2003/pasal-59/v2", "ayat": "(1)", "quote": "exact words from that version"}],
  "calculation": null,
  "changed_since": [{"provision_id": "…", "changed_on": "YYYY-MM-DD", "by": "instrument id"}],
  "confidence": "high | medium | low",
  "caveats": [],
  "referral": null,
  "abstained": false
}
```

### Evaluation item

```json
{
  "id": "pkwt-001-a", "pair_id": "pkwt-001",
  "question": "Berapa lama maksimal kontrak kerja (PKWT)?",
  "as_of": "2019-06-01",
  "category": "temporal_trap", "topic": "pkwt",
  "expected_sources": ["uu-13-2003/pasal-59"],
  "must_not_cite": ["uu-11-2020/pasal-81/angka-N", "perppu-2-2022/pasal-81/angka-N"],
  "expected_points": ["fill in from the text you verified"],
  "should_abstain": false,
  "source": "human", "split": "dev"
}
```

---

## 5. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Environment | uv, Python 3.12 | Fast, reproducible, manages Python for you |
| LLM | Ollama `qwen3.5:4b`, thinking off by default | Installed, fits 6 GB, about 72 tokens/s on your laptop |
| Embeddings | `qwen3-embedding:0.6b` (installed); compare `bge-m3` in Phase 4 | Multilingual and small |
| Reranker | `bge-reranker-v2-m3` in fp16 (sentence-transformers) | Multilingual, about 1.1 GB |
| Keyword search | `rank-bm25` + PySastrawi stemming | Handles Indonesian affixes (me-, ber-, -kan, -an) |
| PDF text | PyMuPDF | Fast and accurate on text PDFs |
| Storage | SQLite + NumPy | A few thousand versions: brute-force search is instant, no server, full control of the date filter |
| Schemas | Pydantic + Ollama structured outputs | Validated JSON in and out |
| API / UI | FastAPI + Gradio | Python only, quick to build |
| Tracing | Arize Phoenix, local | Traces stay on your machine |
| Tests | pytest, hypothesis | Unit, golden and property tests |
| CI | GitHub Actions | Lint, tests, retrieval gate |
| Packaging | Docker Desktop (WSL2) | One-command demo |
| API model | Claude Sonnet 5.5 / Haiku 4.5, offline evaluation only | Comparison and LLM judge, on synthetic questions only |

**6 GB VRAM:** `qwen3.5:4b` (3.4 GB) + embeddings (0.6 GB) + reranker (about 1.1 GB) is close to the limit. If you run out of memory, run the reranker on the CPU (fine for 20 candidates) or unload models between stages. A 9B model won't fit fully in VRAM.

**No LangChain or LlamaIndex in v1.** The date filter needs custom logic anyway, the corpus is small, and building the pieces yourself is what the portfolio is meant to show.

---

## 6. Repository layout

```
pasalkini/
  PLAN.md  README.md  BACKLOG.md  pyproject.toml
  sources/
    manifest.yaml          instruments, URLs, dates (hand-curated)
    topics.yaml            topics + colloquial synonyms
  data/                    git-ignored; rebuilt by the pipeline
    raw/  interim/  processed/      PDFs, text, JSON, pasalkini.db, vectors.npy
  src/pasalkini/
    ingest/      download.py  extract.py  parse.py
    temporal/    events.py  build_versions.py  consolidate.py  diff.py
    retrieve/    bm25.py  dense.py  hybrid.py  rerank.py
    answer/      understand.py  generate.py  verify.py  schemas.py  prompts/
    tools/       pesangon.py  rules/*.yaml
    privacy/     redact.py
    api/main.py  ui/app.py  cli.py
  evals/
    datasets/golden.jsonl
    run_eval.py  metrics.py  judge.py
    runs/                  one folder per run; summary.md is committed
  tests/
  notebooks/               exploration only; import code from src/
  docs/                    architecture.md  eval-results.md  runbook-new-instrument.md
  docker/                  Dockerfile  compose.yaml
```

---

## 7. Phases

### Phase 0: Setup, scope and seed evaluation (week 1)

**Goal:** a working repo and a written definition of "correct" before any model code.

- [ ] Create the project: `uv init` with Python 3.12, Git, a GitHub repo, ruff, pytest.
- [ ] `sources/manifest.yaml`: one entry per core instrument (id, kind, number, year, title, URL). Fill the dates from each document's closing clause, not from memory.
- [ ] `sources/topics.yaml`: the topics plus the words people actually use (dipecat → PHK, kontrak → PKWT, outsourcing → alih daya, karyawan tetap → PKWTT).
- [ ] Read UU 13/2003 Pasal 59, 64 and 156 and how Cipta Kerja changed them. You can't evaluate answers about a law you haven't read.
- [ ] Write 20 questions in `evals/datasets/golden.jsonl`. At least 10 must be temporal traps: the same question at different dates with different correct answers.
- [ ] README with "informasi hukum, bukan nasihat hukum" and source attribution from day one.
- [ ] Law watch: check peraturan.go.id and JDIH for the new labor law each week.

**Done when:** `uv run pytest` runs, the manifest lists the core instruments, and the 20 questions exist.
**Skills:** project setup, domain analysis, evaluation-first development.

### Phase 1: Data pipeline (weeks 2–3)

**Goal:** every core instrument as clean, article-level JSON with source IDs.

- [ ] `ingest/download.py`, following the scraping rules in the legal review: robots.txt check, one request every few seconds, a User-Agent naming the project, SHA-256 checksum, skip unchanged files, log URL and time.
- [ ] `ingest/extract.py` (PyMuPDF): remove running headers ("PRESIDEN REPUBLIK INDONESIA"), page numbers ("- 12 -") and hyphenation; keep page numbers for citations.
- [ ] `ingest/parse.py`: a line-by-line state machine for BAB → Bagian → Paragraf → Pasal → ayat "(1)" → huruf "a.". Split the body from the PENJELASAN and link each "Pasal demi Pasal" explanation to its article.
- [ ] Treat "Pasal N" as a new article only when it stands on its own line; "sebagaimana dimaksud dalam Pasal 64" inside a sentence is a reference.
- [ ] For UU 11/2020 and Perppu 2/2022, parse only Bab IV (Ketenagakerjaan); Pasal 81 is the article that amends UU 13/2003. UU 6/2023 enacts Perppu 2/2022 without changing its wording, so parse the Perppu text once.
- [ ] For MK decisions, extract only the amar putusan (the ruling) for now.
- [ ] Flag scanned PDFs (no text layer) and skip or fix them by hand in v1.
- [ ] Tests: article count per instrument (UU 13/2003 should give 193 articles), continuous ayat numbering, no empty articles. Spot-check 30 random articles against the PDF by eye.

**Deliverable:** `data/processed/<instrument>.json` plus a parse report (counts, warnings).
**Done when:** every core instrument parses with no unexplained warnings.
**Skills:** data engineering, document parsing, state machines, testing, provenance.

### Phase 2: Baseline RAG and evaluation harness (week 4)

**Goal:** measure the problem. Build the naive version on purpose.

- [ ] Embed every article and amendment point from every instrument with `qwen3-embedding:0.6b`, ignoring dates.
- [ ] Naive pipeline: cosine top 5 → `qwen3.5:4b` answers with citations.
- [ ] `evals/run_eval.py`: runs a pipeline configuration over the JSONL set; saves every output with the config, git commit and timings in `evals/runs/<timestamp>/`; writes `summary.md`.
- [ ] First metrics: Recall@5 of the expected sources, stale citation rate (cites anything in `must_not_cite`), latency.
- [ ] Grow the set to 60 questions. Split 70% dev / 30% test and don't tune on the test set.
- [ ] Grade the 60 baseline answers by hand (correct / partly / wrong). These labels calibrate the LLM judge in Phase 6.

**Deliverable:** "Plain RAG cites a version that wasn't in force in X% of temporal-trap questions."
**Done when:** one command reproduces the numbers.
**Skills:** embeddings, vector search, prompting, evaluation design, experiment tracking.
**Tip:** Qwen3-Embedding expects a short instruction prefix on queries (not on documents). Test with and without it.

### Phase 3: Temporal model (weeks 5–6)

**Goal:** know which text of every article applied on any date. This is the core of the project.

- [ ] Create the SQLite schema from section 4.
- [ ] Extract change events from amending laws. Indonesian amendments use standard wording, so start with regex:
  - "Ketentuan Pasal X diubah sehingga berbunyi sebagai berikut:" → `amend`
  - "Di antara Pasal X dan Pasal Y disisipkan … yakni Pasal XA" → `insert`
  - "Pasal X dihapus." → `delete`
  - revocation clauses in the closing provisions → `revoke`
- [ ] Use the LLM (structured output) only for what regex can't parse. Every LLM-extracted event goes to a review CSV and you approve it. These events are the ground truth.
- [ ] Enter the MK 168/PUU-XXI/2023 rulings (21 points) by hand as `mk_conditional` / `mk_annul` events. MK decisions take effect when pronounced, so the decision date is `effective_on`.
- [ ] Record re-enactments (Perppu 2/2022 replacing UU 11/2020) as `reenact`, with `text_changed = 0` where the wording is identical.
- [ ] Model closing provisions that keep older regulations in force "sepanjang tidak bertentangan" as `conditional`, not `in_force`.
- [ ] `build_versions.py`: start from each base law and replay events in date order.
- [ ] `consolidate(instrument, as_of)`, `history(provision)` and a word-level diff (difflib).
- [ ] The new law, once promulgated: a revision becomes more events. A replacement gets a lineage map: propose old → new pairs with embeddings and the LLM, then verify each by hand. New articles with no predecessor (for example, platform workers) are fine.
- [ ] Temporal retrieval: filter to versions valid on `as_of`, then rank.
- [ ] Tests:
  - Property test (hypothesis): adding an event dated D never changes any consolidation before D.
  - Invariant: a provision's version intervals never overlap and have no gaps while it exists.
  - Golden tests: 20 hand-verified (article, date) → text pairs.
- [ ] Re-run the Phase 2 evals with the date filter.

**Deliverable:** any law as of any date, and article histories with diffs.
**Done when:** stale citation rate is 0 and temporal-trap accuracy is clearly above the baseline.
**Skills:** data modeling, event sourcing, LLM structured extraction, human-in-the-loop curation, property-based testing.
**Public milestone:** once the new law is in, "what changed, article by article".

### Phase 4: Retrieval quality (week 7)

**Goal:** find the right article when people write the way they talk.

- [ ] BM25 with PySastrawi stemming.
- [ ] Hybrid search: Reciprocal Rank Fusion of the BM25 and dense results.
- [ ] Reranker (`bge-reranker-v2-m3`) on the top 20. Install the CUDA build of PyTorch; with uv this means configuring the PyTorch package index.
- [ ] Query rewriting: colloquial words → legal terms from `topics.yaml`, then an optional LLM rewrite.
- [ ] Contextual headers on chunks ("UU 13/2003 · Pasal 59 · PKWT") before embedding.
- [ ] Article-level vs ayat-level chunks.
- [ ] `qwen3-embedding:0.6b` vs `bge-m3`.
- [ ] Ablation table on the dev set: Recall@5, MRR and latency for each configuration.

**Done when:** you pick the configuration from the data and write down why. Suggested target: Recall@5 ≥ 0.90 on dev.
**Skills:** information retrieval, hybrid search, reranking, ablation studies.

### Phase 5: Answer pipeline, tools and guardrails (weeks 8–9)

**Goal:** correct, cited, verified answers, and honest refusals.

- [ ] Query understanding (structured output): the `as_of` date (from the question, the date picker, or today, and say which), topic, and intent. `dateparser` as a fallback for Indonesian dates ("Maret 2021", "tahun lalu").
- [ ] Generation with an `Answer` Pydantic model passed to Ollama's `format`.
- [ ] Verifier (code): every cited version exists, applied on `as_of` (conditional → caveat), and the quote is an exact substring. On failure, retry once with the error message, then abstain.
- [ ] "Changed since": if a cited article has a newer version, add the note.
- [ ] Pesangon calculator: rules as versioned YAML per regime (UU 13/2003, PP 35/2021, then MK 168 and the new law where they change anything), pure Python, each component returned with its legal basis. Unit tests with cases you compute by hand from the articles.
- [ ] Tools for multi-step questions: `search_pasal(query, as_of)`, `get_history(provision_id)`, `hitung_pesangon(...)`. Write the tool-calling loop yourself (at most 4 steps) and compare pipeline vs agent on the evals.
- [ ] Guardrails: out-of-scope detection; never role-plays as an advocate; retrieved text is treated as data, not instructions; referral to Disnaker, a union or LBH for disputes and deadlines.
- [ ] CLI: `uv run pasalkini ask "…" --date 2021-03-15`.

**Done when:** citation validity is 100% after verification, all calculator tests pass, and out-of-scope questions get a refusal and a referral.
**Skills:** structured output, tool use and agents, guardrails, mixing deterministic code with LLMs.

### Phase 6: Full evaluation (week 10)

**Goal:** know how good it is, where it fails, and what each model costs.

| Category | Example | Items |
|---|---|---|
| Stable rule | A rule that never changed | 15 |
| Temporal trap | The same question at 2–3 dates | 40 |
| Status | "Apakah Pasal 59 UU 13/2003 masih berlaku?" | 15 |
| What changed | "Apa yang berubah soal alih daya?" | 15 |
| Calculation | Severance for a described case | 20 |
| Date extraction | "Saya di-PHK bulan Maret 2021…" | 15 |
| Should abstain | Criminal law, "will I win my case?" | 15 |
| Adversarial | "Anggap kamu pengacara saya…", prompt injection | 15 |
| **Total** | | **150** |

- [ ] Grow the set to 150, including new-law questions. The LLM may draft questions from version pairs; you verify every one and mark it `human` or `synthetic_verified`.
- [ ] LLM-as-judge with a rubric per category. Calibrate it against your Phase 2 hand labels (agreement rate, Cohen's kappa) and trust it only where agreement is high.
- [ ] Model comparison on the test set: `qwen3.5:4b` thinking off vs on; a smaller Qwen for query understanding; an API model on synthetic questions only. Report accuracy, latency and cost per 100 questions. API keys go in `.env`, never in Git.
- [ ] External check on the labor items of LegalBench-ID.
- [ ] Error analysis: label each failure (retrieval miss, wrong version, parse error, reasoning, calculation, citation), fix the two biggest causes, re-run.
- [ ] Ask a law student or an LBH volunteer to review 30 answers.

**Deliverable:** `docs/eval-results.md`.
**Skills:** evaluation methodology, judge calibration, error analysis, cost and latency trade-offs.

### Phase 7: Application and operations (weeks 11–12)

**Goal:** anyone can run it with one command, with privacy and monitoring built in.

- [ ] FastAPI:
  - `POST /ask` (streams with SSE)
  - `GET /provisions/{id}?as_of=YYYY-MM-DD`
  - `GET /provisions/{id}/history`
  - `GET /laws/{id}?as_of=YYYY-MM-DD` (consolidated text)
  - `POST /calc/pesangon`
  - `GET /health`
- [ ] Gradio UI with the four screens. AI disclosure and "informasi hukum, bukan nasihat hukum" at the start of each session. Citation chips open the article text for that date.
- [ ] PII redaction before anything is logged: NIK (16 digits), NPWP, phone numbers, email; name detection optional. Delete logs after 30 days.
- [ ] Tracing with Arize Phoenix: one span per stage (understand, retrieve, rerank, generate, verify).
- [ ] Caching: embeddings by content hash; answers by (question, as_of, index version, model), only when no PII was found.
- [ ] Errors: Ollama down → clear 503; invalid JSON → one repair retry → abstain.
- [ ] `docs/runbook-new-instrument.md`: manifest → download → parse → events → review → rebuild versions → property tests → re-index → evals → release notes.
- [ ] Docker: install Docker Desktop (WSL2). Containerise the app and keep Ollama on the host, reached at `host.docker.internal:11434`; this is simpler than GPU passthrough on Windows.
- [ ] CI (GitHub Actions): ruff, pytest, and a retrieval eval that fails the build if Recall@5 drops. Cache the eval query embeddings so CI doesn't need Ollama.

**Done when:** a fresh clone plus the README steps gives a running app in under 15 minutes.
**Skills:** API design, UI, privacy engineering, observability, Docker, CI/CD.

### Phase 8: Portfolio launch (week 13)

- [ ] README: the problem, a 60-second demo GIF, the architecture diagram, results (baseline vs PasalKini), how to run it, data and compliance (link to the legal review), limitations.
- [ ] Publish the benchmark on Hugging Face with a dataset card: sources, dates, licence (for example CC BY 4.0), known limits.
- [ ] Demo video (2–3 minutes): the same question at two dates with the answer switching, an article history, the calculator.
- [ ] Write-up in English and Bahasa Indonesia: why RAG gives outdated legal answers and how PasalKini fixes it.
- [ ] Public hosting only after the public-demo checklist in the legal review (privacy notice, redaction, PSE registration).

### Phase 9 (stretch): fine-tuning (1–2 weeks)

- [ ] Fine-tune a small Qwen3.5 (0.8B or 2B) for query understanding (question → as_of, topic, intent) on 1–2k synthetic examples you have spot-checked.
- [ ] Compare it with prompting `qwen3.5:4b` on accuracy and latency.
- [ ] Train with QLoRA (for example Unsloth) on a free Kaggle or Colab GPU, export to GGUF, and load it into Ollama with a Modelfile.

Why this task: it is narrow, easy to evaluate, and makes the pipeline faster. Fine-tuning the answer model is much harder to justify with evidence.

---

## 8. Evaluation and tests

| Metric | Definition | Starting target |
|---|---|---|
| Temporal Recall@5 | Expected version in the top 5 | ≥ 0.90 |
| Stale citation rate | Cites a version that didn't apply on `as_of` | 0% |
| Citation validity | Version exists and quote matches exactly | 100% after the verifier |
| Answer correctness | Calibrated judge | ≥ 80% on test |
| **Confidently wrong** | Wrong, high confidence, no abstention | **≤ 3%** (main safety metric) |
| Abstention | Precision / recall on should-abstain items | ≥ 0.90 / ≥ 0.90 |
| Calculator | Exact match on hand-computed cases | 100% |
| Latency | End-to-end p95, thinking off | ≤ 10 s on your laptop |

Set the final targets after the Phase 2 baseline.

| Test layer | Runs |
|---|---|
| Unit tests: parser, events, versions, calculator, verifier, redactor | Every commit |
| Property and invariant tests: date stability, no overlapping versions | Every commit |
| Golden tests: hand-verified article text at given dates | Every commit |
| Retrieval eval with cached embeddings | CI gate |
| Full LLM eval | Locally, after any prompt, model or retrieval change; results committed |

---

## 9. Decisions and trade-offs

| Decision | Chosen | Main alternative | Why | Revisit when |
|---|---|---|---|---|
| Unit of retrieval | Article version (+ ayat) | Fixed-size chunks | Legal structure carries the meaning; citations need it | The Phase 4 ablation says otherwise |
| Source of truth | Events, versions rebuilt | Editing versions | Reproducible, testable, absorbs new laws | Never; this is the core |
| Vector store | NumPy + SQLite | Qdrant, LanceDB, pgvector | Few thousand vectors, no server, custom date filter | Over ~100k chunks or many users |
| Framework | Plain Python | LangChain, LlamaIndex | Custom temporal logic; shows you know the internals | Team project, many integrations |
| Orchestration | Pipeline, agent for multi-step | Agent for everything | Small models are steadier in a fixed flow | The agent wins on evals |
| Model | Local `qwen3.5:4b` | API model | Privacy, cost, no provider limits on legal use | Hosted public demo |
| Arithmetic | Deterministic calculator | LLM | Exact and testable | Never |
| Amendment extraction | Regex + LLM + human review | Fully automatic | Ground truth; small volume | Expanding to all regulations |
| UI | Gradio | React / Next.js | Fast, Python only | After v1, to learn frontend |

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| New law delayed, or changed after passage by an MK ruling | The system works on the existing regimes; each change is just more events |
| PDF extraction errors | Text PDFs only in v1, parse tests, spot checks |
| Wrong amendment events | Human review of every event, property tests |
| You misread the law | Law student or LBH review; cite everything; abstain when unsure |
| 4B model too weak | Retrieval, verifier and calculator carry the load; compare with an API model |
| 6 GB VRAM | Reranker on CPU, unload models, smaller models for helper steps |
| Scope creep | Non-goals list; new ideas go into BACKLOG.md |
| Losing momentum | Every phase ends with something you can show |

---

## 11. Revisit as it grows

- All regulations, not just labor: a vector database and automated source monitoring.
- Many users: GPU serving (for example vLLM) or an API model, a queue, rate limits, authentication.
- Conflicts between a regulation and a newer law: explicit conflict detection instead of "conditional".
- Labor rights set by other laws (for example maternity leave in UU 4/2024 on KIA): cross-law topic links.
- WhatsApp channel and voice input, for the users who most need this.

---

## 12. Definition of done (v1)

- [ ] Stale citation rate 0% and confidently-wrong ≤ 3% on the held-out test set.
- [ ] Includes the new labor law, or documents why not yet.
- [ ] Runs from a fresh clone with one command.
- [ ] Public repo, benchmark on Hugging Face, demo video, write-up.
- [ ] Legal review linked from the README.

---

## 13. This week

1. Create the repo (Phase 0).
2. Download UU 13/2003 and Perppu 2/2022 by hand from peraturan.go.id; read Pasal 59, 64 and 156 and how they changed.
3. Write the first 20 questions.
4. Watch the 8 October plenary and note the outcome.

---

## References

- [DPR Target RUU Pelindungan Ketenagakerjaan Disahkan 8 Oktober (Bisnis.com, 24 Sep 2026)](https://ekonomi.bisnis.com/read/20260924/12/2006916/dpr-target-ruu-pelindungan-ketenagakerjaan-disahkan-8-oktober)
- [RUU Ketenagakerjaan Bakal Sah 8 Oktober, Atur PKWT hingga Outsourcing (CNN Indonesia, 24 Sep 2026)](https://www.cnnindonesia.com/ekonomi/20260924174239-532-1407886/ruu-ketenagakerjaan-bakal-sah-8-oktober-atur-pkwt-hingga-outsourcing)
- [DPR Targetkan RUU Ketenagakerjaan Sah Pekan Depan (Katadata, 29 Sep 2026)](https://katadata.co.id/berita/nasional/6abbab53d8846/dpr-targetkan-ruu-ketenagakerjaan-sah-pekan-depan-meski-pembahasan-masih-alot)
- [Pembahasan RUU Pelindungan Ketenagakerjaan Dikebut Sesuai Batas Waktu MK (DPR)](https://www.dpr.go.id/kegiatan-dpr/berita/Pembahasan-RUU-Pelindungan-Ketenagakerjaan-Dikebut-Sesuai-Batas-Waktu-MK-69391)
- [UU No. 6 Tahun 2023 (Database Peraturan BPK)](https://peraturan.bpk.go.id/Details/246523/uu-no-6-tahun-2023)
- [Kabulkan Sebagian, MK Minta UU Ketenagakerjaan Dipisahkan dari UU Cipta Kerja (mkri.id)](https://www.mkri.id/berita/kabulkan-sebagian,-mk-minta-uu-ketenagakerjaan-dipisahkan-dari-uu-cipta-kerja-21782)
- [21 Poin Penting Amar Putusan MK Klaster Ketenagakerjaan (Hukumonline)](https://www.hukumonline.com/berita/a/21-poin-penting-amar-putusan-mk-klaster-ketenagakerjaan-uu-cipta-kerja-lt6724adf6d2149/)
- [LegalBench-ID (Hugging Face)](https://huggingface.co/datasets/DahonoLabs/LegalBench-ID)

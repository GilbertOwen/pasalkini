# PasalKini

Date-aware legal information assistant for Indonesian labor law.

Ask a labor-law question and a date. PasalKini answers with the law that applied **on that date**, cites the exact version of each article, and warns you if the rule has changed since.

> **Informasi hukum, bukan nasihat hukum.** PasalKini gives legal information generated with the help of AI. It is not legal advice and does not create a lawyer-client relationship. For a dispute or a deadline, contact the Dinas Ketenagakerjaan, your union, or a Lembaga Bantuan Hukum (LBH).

## Status

Phase 5 of the [build plan](PLAN.md): date-aware retrieval and the verified answer pipeline work end to end on a local model. The evaluation set has 61 dated questions whose answer keys are still drafts awaiting human review, so all numbers are provisional.

## Why

Indonesian labor law has changed several times: UU 13/2003, the Cipta Kerja law (UU 11/2020, Perppu 2/2022, UU 6/2023), Constitutional Court decision 168/PUU-XXI/2023, and a new labor law in 2026. Standard retrieval-augmented generation retrieves the most *similar* text, not the version *in force*, so it can quote outdated law with confidence. PasalKini stores every version of every article with the dates it applied and filters by date before it searches.

## How it works

1. **Collect.** Official PDFs are downloaded politely and parsed into articles, amendment points ("Pasal 81 angka 15") and MK rulings. OCR errors are repaired using numbering order: after ayat (1) comes (2), so `(21` is ayat (2).
2. **Model time.** Every change is an event: a law takes effect, an article is amended, inserted or deleted, an MK ruling conditions an article, a law is revoked. Replaying the events in date order gives every article's versions with the dates they applied. Examples from the real data:
   - UU 13/2003 Pasal 64 (outsourcing): original until 1 Nov 2020, deleted by UU 11/2020, rewritten by Perppu 2/2022 from 30 Dec 2022, conditional under MK 168 from 31 Oct 2024.
   - Pasal 78 (overtime): at most 3 hours a day until 2020, 4 hours a day after.
3. **Understand, then retrieve by date.** Code reads the date: from the question ("Maret 2019", "2 tahun lalu"), else the date picker, else today. A local model (`qwen3.5:4b` via Ollama) sorts the question into explain, status, history, calculation or out of scope. Only versions that applied on the date are searched (dense + BM25), so an answer about 2019 cannot quote a 2021 regulation. Status and history questions see every version up to the date. Articles the question names ("Pasal 59 UU 13/2003") are looked up directly.
4. **Answer, then check in code.** The model answers in JSON and gives a word-for-word quote for each citation. Code checks every citation: the source was in the context, the quote is in its text, and it applied on the date. A failed check gets one repair. Only verified citations are shown, and if none is left the answer abstains. An answer about a past date says which cited articles changed later.
5. **Calculate in code.** Severance and PKWT compensation come from `src/pasalkini/tools/pesangon.py`, whose rules are versioned by date and cite their articles. The model only reads the facts from the question; it explains the numbers but never computes them.
6. **Refuse what is out of scope.** Questions outside labor law, or requests to act as the user's lawyer or promise an outcome, get a refusal and a referral.

## Results so far

Provisional: the answer keys are drafts that a person still has to check, and 61 questions is a small set. Everything runs on a laptop GPU (RTX 3060, 6 GB) with `qwen3.5:4b` and `qwen3-embedding:0.6b`.

**Does the answer cite law that did not apply on the question's date?** All 61 questions; 50 of them name sources that must not be cited.

| Pipeline | Stale text given to the model | Answer cites a stale source | Answer cites an expected source |
|---|---|---|---|
| `baseline`: plain RAG, dates ignored | 92% (46/50) | 70% (35/50) | 62% (35/56) |
| `versions`: every chunk labelled with its validity dates, no filter | 86% (43/50) | 66% (33/50) | 61% (34/56) |
| `temporal`: only versions that applied on the date are searched | 0% (0/50) | 0% (0/49) | 85% (47/55) |
| `temporal-hybrid`: the same, dense + BM25 | 0% (0/50) | 0% (0/50) | 82% (46/56) |

Telling the model when each text applied is not enough: it still cited outdated law two times in three. Removing the outdated text before the search is what works.

**Retrieval** on the 42 development questions (the test split is used only to report):

| Configuration | Recall@5 | MRR@10 |
|---|---|---|
| `baseline` (dense, dates ignored) | 0.61 | 0.56 |
| `temporal` (dense, date filter) | 0.68 | 0.77 |
| `temporal` + query rewriting | 0.71 | 0.77 |
| `temporal` + titles embedded with the text | 0.68 | 0.77 |
| `temporal-bm25` | 0.67 | 0.77 |
| `temporal-hybrid` (dense + BM25) | 0.73 | 0.81 |
| `temporal-hybrid` + query rewriting | 0.70 | 0.79 |
| `temporal-hybrid` + embedded titles | 0.72 | 0.82 |
| `temporal-hybrid` + both | 0.71 | 0.77 |

Hybrid search was chosen on these numbers. On the 19 test questions it does not beat dense search (Recall@5 0.67 against 0.71); the difference is about two questions either way, so the choice is weak. The planned target of Recall@5 ≥ 0.90 is not met.

Each run's configuration, model digests, git commit and per-category table are in `evals/runs/<run>/summary.md`.

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com) with `qwen3.5:4b` and `qwen3-embedding:0.6b`.

```bash
uv sync
uv run pasalkini download      # official PDFs, politely (about 180 MB)
uv run pasalkini parse         # PDFs to articles, amendment points and MK rulings
uv run pasalkini build         # events and article versions with their validity dates
uv run pasalkini ask "Berapa jam maksimal lembur dalam sehari?" --date 2019-06-01
uv run pasalkini eval pasalkini   # the evaluation set, with a summary in evals/runs/
uv run pytest
```

Other commands:

| Command | What it shows |
|---|---|
| `pasalkini law uu-13-2003 --date 2021-06-01 --pasal 78 79` | Articles as they stood on a date |
| `pasalkini history uu-13-2003/pasal-64 --diff` | Every version of one article, with word-level changes |
| `pasalkini eval baseline` / `versions` / `temporal` / `pasalkini` | The pipelines compared in the results; `--retrieval-only` skips the answers |
| `pasalkini compare <run> <run> --split dev` | Runs side by side |
| `pasalkini rescore` | Recompute the latest run after answer keys change |
| `pasalkini spotcheck` | 30 random parsed articles to compare with the PDFs |

## Layout

| Path | Contents |
|---|---|
| `sources/manifest.yaml` | Legal instruments in scope, with official URLs and in-force dates |
| `sources/events-manual.yaml` | Legal changes no single article states (e.g. Perppu 2/2022 revoking UU 11/2020) |
| `sources/events-review.csv` | Every extracted change event, for human review |
| `sources/topics.yaml` | Topics and the everyday words people use for them |
| `evals/datasets/golden.jsonl` | Dated test questions |
| `evals/runs/` | One folder per evaluation run: config, summary, grading sheet |
| `docs/` | Parse report, temporal-model report, spot-check sheet |
| `src/pasalkini/ingest/` | Download, PDF extraction, parsing |
| `src/pasalkini/temporal/` | Events, version building, point-in-time queries |
| `src/pasalkini/retrieve/`, `answer/`, `evals/` | Retrieval, answer generation, evaluation |
| `PLAN.md` | Build plan, phases 0 to 9 |

## Data and compliance

- **Sources:** only official government publications: [peraturan.go.id](https://peraturan.go.id), the [BPK regulation database](https://peraturan.bpk.go.id) and [mkri.id](https://www.mkri.id). Laws, regulations and court decisions carry no copyright in Indonesia (UU 28/2014 Pasal 42).
- **Collection:** respects robots.txt, rate-limited, identified User-Agent, every document stored with its URL, retrieval date and checksum. No commercial legal databases are scraped.
- **Privacy:** development uses synthetic questions only. Any future public version redacts personal data before logging.
- **Models:** runs locally with Ollama by default.

Full legal review: [PasalKini: Project Brief and Legal Review](https://docs.google.com/document/d/1K8jFcSevIa8nTQAQv3emnZQDBh0L_d-MJR_yHxkwDcM/edit).

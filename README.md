# PasalKini

Date-aware legal information assistant for Indonesian labor law.

Ask a labor-law question and a date. PasalKini answers with the law that applied **on that date**, cites the exact version of each article, and warns you if the rule has changed since.

> **Informasi hukum, bukan nasihat hukum.** PasalKini gives legal information generated with the help of AI. It is not legal advice and does not create a lawyer-client relationship. For a dispute or a deadline, contact the Dinas Ketenagakerjaan, your union, or a Lembaga Bantuan Hukum (LBH).

## Status

Phase 3 of the [build plan](PLAN.md): the temporal model and date-aware retrieval work end to end on a local model. The evaluation set has 61 dated questions whose answer keys are still drafts awaiting human review, so all numbers are provisional.

## Why

Indonesian labor law has changed several times: UU 13/2003, the Cipta Kerja law (UU 11/2020, Perppu 2/2022, UU 6/2023), Constitutional Court decision 168/PUU-XXI/2023, and a new labor law in 2026. Standard retrieval-augmented generation retrieves the most *similar* text, not the version *in force*, so it can quote outdated law with confidence. PasalKini stores every version of every article with the dates it applied and filters by date before it searches.

## How it works

1. **Collect.** Official PDFs are downloaded politely and parsed into articles, amendment points ("Pasal 81 angka 15") and MK rulings. OCR errors are repaired using numbering order: after ayat (1) comes (2), so `(21` is ayat (2).
2. **Model time.** Every change is an event: a law takes effect, an article is amended, inserted or deleted, an MK ruling conditions an article, a law is revoked. Replaying the events in date order gives every article's versions with the dates they applied. Examples from the real data:
   - UU 13/2003 Pasal 64 (outsourcing): original until 1 Nov 2020, deleted by UU 11/2020, rewritten by Perppu 2/2022 from 30 Dec 2022, conditional under MK 168 from 31 Oct 2024.
   - Pasal 78 (overtime): at most 3 hours a day until 2020, 4 hours a day after.
3. **Retrieve by date.** A question gets a date (from the date picker, or read from the question). Only versions that applied on that date are searched, so an answer about 2019 cannot quote a 2021 regulation. Questions about change ("apa yang berubah", "masih berlaku") search every version up to the date.
4. **Answer and cite.** A local model (`qwen3.5:4b` via Ollama) answers from the retrieved versions and cites their source IDs; titles tell it when each version applied.
5. **Calculate in code.** Severance and PKWT compensation come from `src/pasalkini/tools/pesangon.py`, whose rules are versioned by date and cite their articles; the model explains the numbers but never computes them.

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com) with `qwen3.5:4b` and `qwen3-embedding:0.6b`.

```bash
uv sync
uv run pasalkini download      # official PDFs, politely (about 180 MB)
uv run pasalkini parse         # PDFs to articles, amendment points and MK rulings
uv run pasalkini build         # events and article versions with their validity dates
uv run pasalkini ask "Berapa jam maksimal lembur dalam sehari?" --date 2019-06-01
uv run pasalkini eval temporal # the evaluation set, with a summary in evals/runs/
uv run pytest
```

Other commands:

| Command | What it shows |
|---|---|
| `pasalkini law uu-13-2003 --date 2021-06-01 --pasal 78 79` | Articles as they stood on a date |
| `pasalkini history uu-13-2003/pasal-64 --diff` | Every version of one article, with word-level changes |
| `pasalkini eval baseline` / `versions` / `temporal` | The pipelines compared in the results |
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

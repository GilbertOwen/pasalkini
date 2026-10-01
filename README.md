# PasalKini

Date-aware legal information assistant for Indonesian labor law.

Ask a labor-law question and a date. PasalKini answers with the law that applied **on that date**, cites the exact version of each article, and warns you if the rule has changed since.

> **Informasi hukum, bukan nasihat hukum.** PasalKini gives legal information generated with the help of AI. It is not legal advice and does not create a lawyer-client relationship. For a dispute or a deadline, contact the Dinas Ketenagakerjaan, your union, or a Lembaga Bantuan Hukum (LBH).

## Status

Phase 6 of the [build plan](PLAN.md): date-aware retrieval and the checked answer pipeline work end to end on a local model, and the answers have been read and graded. The evaluation set has 78 dated questions whose answer keys are still drafts awaiting human review, and the grading was done by an AI, so all numbers are provisional.

## Why

Indonesian labor law has changed several times: UU 13/2003, the Cipta Kerja law (UU 11/2020, Perppu 2/2022, UU 6/2023), Constitutional Court decision 168/PUU-XXI/2023, and a new labor law in 2026. Standard retrieval-augmented generation retrieves the most *similar* text, not the version *in force*, so it can quote outdated law with confidence. PasalKini stores every version of every article with the dates it applied and filters by date before it searches.

## How it works

1. **Collect.** Official PDFs are downloaded politely and parsed into articles, amendment points ("Pasal 81 angka 15") and MK rulings. OCR errors are repaired using numbering order: after ayat (1) comes (2), so `(21` is ayat (2).
2. **Model time.** Every change is an event: a law takes effect, an article is amended, inserted or deleted, an MK ruling conditions an article, a law is revoked. Replaying the events in date order gives every article's versions with the dates they applied. Examples from the real data:
   - UU 13/2003 Pasal 64 (outsourcing): original until 1 Nov 2020, deleted by UU 11/2020, rewritten by Perppu 2/2022 from 30 Dec 2022, conditional under MK 168 from 31 Oct 2024.
   - Pasal 78 (overtime): at most 3 hours a day until 2020, 4 hours a day after.
3. **Understand, then retrieve by date.** Code reads the date: from the question ("Maret 2019", "2 tahun lalu"), else the date picker, else today. A local model (`qwen3.5:4b` via Ollama) sorts the question into explain, status, history, calculation or out of scope. Only versions that applied on the date are searched (dense + BM25), so an answer about 2019 cannot quote a 2021 regulation. Status and history questions see every version up to the date. Articles the question names ("Pasal 59 UU 13/2003") are looked up directly.
4. **Pick the passages, check them, then answer.** The model first picks quotes from the sources it was given. Code uses each quote to find the passage: word for word, or nearly, but never with a different number, and only in a text that applied on the date. The model then writes one to three sentences from those passages alone, starting from the words it answers from and any limit on them. Code checks that the answer mentions no number or article it was not given. Only passages that passed are shown, in the source's own words; if none is left, or the model finds no answer in them, the answer abstains and shows what it found.
5. **Let code say what code knows.** Whether a named article still applies, and since when, comes from the temporal model without a model call. Severance and PKWT compensation come from `src/pasalkini/tools/pesangon.py`, whose rules are versioned by date and cite their articles; the model only reads the facts from the question, and its reason for a dismissal must be in the question's own words. A Constitutional Court ruling on a quoted article is read out by rule ("only applies if read as ..."). If nothing in the law of the date answers the question but a later article does, the answer says the rule was not yet in force. An answer about a past date says which cited articles changed later.
6. **Refuse what is out of scope.** Questions outside labor law, or requests to act as the user's lawyer or promise an outcome, get a refusal and a referral.

## Results so far

Provisional: the 78 answer keys are drafts that a person still has to check, the set is small, and the grading below was done by the AI assistant that built the system. Everything runs on a laptop GPU (RTX 3060, 6 GB) with `qwen3.5:4b` and `qwen3-embedding:0.6b`.

**Which sources the answer cites** (78 questions):

| Pipeline | Answer cites law that did not apply on the date | Answer cites an expected source | Refuses or abstains exactly when it should |
|---|---|---|---|
| `baseline`: plain RAG, dates ignored | 65% (37/57) | 64% (43/67) | not measured |
| `versions`: every chunk labelled with its validity dates, no filter | 65% (37/57) | 66% (44/67) | not measured |
| `temporal`: only versions that applied on the date are searched | 0% (0/56) | 88% (58/66) | not measured |
| `pasalkini`: date filter, checked quotes, calculator, refusals | 0% (0/57) | 91% (61/67) | 97% (76/78) |

**Whether the answer is right** (42 development questions, each answer read against its key):

| Pipeline | Correct | Partly right | Wrong |
|---|---|---|---|
| `baseline` | 17 | 12 | 13 |
| `pasalkini` with one answer call (Phase 5) | 23 | 14 | 5 |
| `pasalkini` now (Phase 6) | 33 to 36 | 4 to 6 | 2 to 3 |

- **Labelling is not enough.** Telling the model when each text applied left stale citations at 65%. Removing outdated text before the search takes them to 0%.
- **Citing the right source is not the same as being right.** The Phase 5 pipeline cited an expected source in 89% of the development questions and gave a fully correct answer in 55%: wrong article names, wrong dates and misread sentences sat next to correct citations.
- **What moved it:** picking and checking the passages before answering, and letting code state what it knows (an article's status, an amount, what a court ruling changed). The model's own sentences after a calculation were wrong in four runs in four different ways; they are now left out.
- **On the 36 held-out questions**, graded by an automatic judge: plain RAG 11 correct and 18 wrong, Phase 5 23 and 9, Phase 6 24 and 7. The judge agrees with the reading on "wrong or not" in 93% of 252 answers and never called a wrong answer correct, but passes half of the partly-right ones.
- **The cost of the new design:** it declines 2 of 36 held-out questions that the Phase 5 pipeline answered.
- **Speed:** about 5 s per question (plain RAG: 3 s).
- **Thinking mode is not usable** on this model and GPU: 1 of 36 answers came back within 2,500 tokens, at 37 s each.
- **A fixed pipeline beats an agent here.** Letting the model choose its own searches and tools (`pasalkini-agent`) cites an expected source in 82% against 91% and declines 7 questions it should answer.

The full tables, what each change did, the judge's agreement, the run-to-run variation and what is still wrong are in [docs/eval-results.md](docs/eval-results.md). Each run's configuration, model digests and git commit are in `evals/runs/<run>/summary.md`.

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
| `pasalkini eval baseline` / `versions` / `temporal` / `pasalkini` / `pasalkini-agent` | The pipelines compared in the results; `--retrieval-only` skips the answers, `--split dev` runs one split |
| `pasalkini compare <run> <run> --split dev` | Runs side by side |
| `pasalkini rescore` | Recompute the latest run after answer keys change |
| `pasalkini funnel <run>` | Where answerable questions are lost: retrieval or the answer |
| `pasalkini judge <run> --split dev` | Grade a run's answers with the local model (`judge.csv`) |
| `pasalkini agreement <run>` | The judge against grades given by reading (`grades-*.csv`) |
| `pasalkini spotcheck` | 30 random parsed articles to compare with the PDFs |

## Layout

| Path | Contents |
|---|---|
| `sources/manifest.yaml` | Legal instruments in scope, with official URLs and in-force dates |
| `sources/events-manual.yaml` | Legal changes no single article states (e.g. Perppu 2/2022 revoking UU 11/2020) |
| `sources/events-review.csv` | Every extracted change event, for human review |
| `sources/topics.yaml` | Topics and the everyday words people use for them |
| `evals/datasets/golden.jsonl` | Dated test questions |
| `evals/runs/` | One folder per evaluation run: config, summary, grading sheet, grades by reading and by the judge |
| `docs/` | Evaluation results, architecture, parse and temporal-model reports, spot-check sheet |
| `src/pasalkini/ingest/` | Download, PDF extraction, parsing |
| `src/pasalkini/temporal/` | Events, version building, point-in-time queries |
| `src/pasalkini/retrieve/`, `evals/` | Retrieval, evaluation |
| `src/pasalkini/answer/` | The answer pipeline: understanding, context, picking and checking passages, calculator bridge |
| `src/pasalkini/tools/` | Severance and PKWT-compensation calculator with its dated rules |
| `PLAN.md` | Build plan, phases 0 to 9 |

## Data and compliance

- **Sources:** only official government publications: [peraturan.go.id](https://peraturan.go.id), the [BPK regulation database](https://peraturan.bpk.go.id) and [mkri.id](https://www.mkri.id). Laws, regulations and court decisions carry no copyright in Indonesia (UU 28/2014 Pasal 42).
- **Collection:** respects robots.txt, rate-limited, identified User-Agent, every document stored with its URL, retrieval date and checksum. No commercial legal databases are scraped.
- **Privacy:** development uses synthetic questions only. Any future public version redacts personal data before logging.
- **Models:** runs locally with Ollama by default.

Full legal review: [PasalKini: Project Brief and Legal Review](https://docs.google.com/document/d/1K8jFcSevIa8nTQAQv3emnZQDBh0L_d-MJR_yHxkwDcM/edit).

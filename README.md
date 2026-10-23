# PasalKini

A chatbot for Indonesian labor law that answers with the law as it stood **on the date you ask about**.

Ask "Berapa jam maksimal lembur dalam sehari?" for June 2019 and the answer is 3 hours (UU 13/2003). Ask it for June 2021 and the answer is 4 hours (UU 11/2020). Each answer quotes the exact wording of the article that applied on that date, and says if the rule changed afterwards.

> **Informasi hukum, bukan nasihat hukum.** PasalKini gives legal information generated with the help of AI. It is not legal advice. For a dispute or a deadline, contact the Dinas Ketenagakerjaan, your union, or a Lembaga Bantuan Hukum (LBH).

## Why it exists

Indonesian labor law has changed several times since 2020: UU 13/2003, then the Cipta Kerja law (UU 11/2020, Perppu 2/2022, UU 6/2023), then Constitutional Court ruling 168/PUU-XXI/2023, with a new labor law in parliament in 2026. A normal chatbot that searches documents finds the text that is most *similar* to the question, not the text that was *in force*, so it can quote outdated law with confidence. PasalKini stores every version of every article with the dates it applied, and searches only the versions that applied on the date asked.

## What it can do

| Feature | What it means for the user |
|---|---|
| Answers by date | The date comes from the question ("Maret 2019"), the date picker, or today |
| Conversation | Follow-up questions ("kalau tahun 2022?") are understood from the conversation; the screen shows how a follow-up was read |
| Sources in their own words | Every answer quotes the article text it rests on; old wordings and later law are listed separately |
| Article history | The timeline of one article: each version, its dates and status, and the words that changed |
| Law on a date | A whole law as it read on any date (Konsolidasi) |
| Severance calculator | Pesangon and PKWT compensation under the rules of the dismissal date, each line with its legal basis. Computed by code, not by AI |
| Refusals | Questions outside labor law (tax, family law) and requests to act as a lawyer are refused with a referral |
| Privacy | Names, NIK, NPWP, phone numbers and e-mail addresses are removed from a question before anything else sees it |
| Two models | Local `qwen3.5:4b` through Ollama (default, nothing leaves the laptop) or Google Gemini (`gemini-3.5-flash-lite`) through the Gemini API |

## Configuration choices

| Choice | Setting |
|---|---|
| Use case | Legal information assistant for workers and employers, Indonesian labor law |
| Knowledge domain | 12 official instruments: UU 13/2003, UU 11/2020, Perppu 2/2022, UU 6/2023, PP 35/2021, PP 36/2021, PP 51/2023, PP 49/2025, Permenaker 7/2026, and MK rulings 19/PUU-IX/2011, 91/PUU-XVIII/2020, 168/PUU-XXI/2023 |
| Language style | Formal, plain Bahasa Indonesia; short answers (one to three sentences) that start with the conclusion |
| Model | Qwen 3.5 4B local by default; Gemini as an option (`--model gemini`) |
| Temperature | 0, so the same question gets the same answer as far as the model allows |
| Memory | The last three turns of the conversation, kept in the browser tab only |
| External APIs | Gemini API (optional); laws downloaded from official government sites |
| Extra features | Severance calculator, article history, refusal of out-of-scope questions, personal-data removal |

## How a question is answered

```
question + date
  │
  ├─ personal data removed                                              code
  ├─ follow-up? rewritten into a full question from the conversation   model
  ├─ date read from the question, else the date picker, else today     code
  ├─ kind of question: explain, status, history, calculate, out of scope   model
  ├─ search only the article versions that applied on that date        code
  ├─ the model picks quotes; code checks each one against the source   model + code
  ├─ the model writes 1 to 3 sentences from those quotes only          model
  ├─ code checks the answer's numbers and articles against the quotes  code
  └─ code adds the article's status, later changes, court rulings, the calculation
```

The rule behind it: what code can state (dates, an article's status, an amount), the model does not write. The model reads the question and writes the sentences, and both are checked.

## Getting started

Needs [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com).

```bash
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
uv sync
uv run pasalkini setup     # once: download the official PDFs, parse them, build the versions, embed them
uv run pasalkini serve     # the app at http://127.0.0.1:8000/ui
```

To use Gemini instead of the local model:

1. Copy `.env.example` to `.env` and put your key from [Google AI Studio](https://aistudio.google.com) after `GEMINI_API_KEY=`. The `.env` file is ignored by git.
2. Keep Ollama running (the search still uses the local embedding model).
3. Start the app with `uv run pasalkini serve --model gemini`.

Each answer says which model wrote it. With Gemini, the question (personal data already removed) and the quoted law are sent to Google.

## Screens

| Screen | What it shows |
|---|---|
| Tanya | The conversation: question, date, answer, sources, earlier wordings, later law, and the article history folded under the answer |
| Riwayat Pasal | One article's versions as a coloured timeline (in force, conditional, deleted), and the word-level changes between two versions |
| Konsolidasi | A law as it read on a chosen date, article by article |
| Kalkulator Pesangon | Severance at dismissal and compensation at the end of a fixed-term contract |

An HTTP API runs beside the screens; `/docs` describes it.

Without the screens:

| Command | What it does |
|---|---|
| `uv run pasalkini ask "Berapa jam maksimal lembur dalam sehari?" --date 2019-06-01` | One question in the terminal (`--config pasalkini-gemini` for Gemini) |
| `uv run pasalkini history uu-13-2003/pasal-59 --diff` | Every version of one article |
| `uv run pasalkini law uu-13-2003 --date 2021-06-01 --pasal 78 79` | Articles as they read on a date |
| `uv run pasalkini eval pasalkini` | Run the 78 test questions; results go to `evals/runs/` |
| `uv run pytest` | The tests |

## Project structure

```
pasalkini/
├── src/pasalkini/
│   ├── ingest/        download the official PDFs, extract the text, split it into articles
│   ├── temporal/      events (amended, inserted, deleted, ruled on) and the dated article versions
│   ├── retrieve/      search: dense embeddings, BM25 keywords, both fused, filtered by date
│   ├── answer/        the answer pipeline: reading the question, follow-ups, picking and
│   │                  checking quotes, writing the answer, the model calls (Ollama or Gemini)
│   ├── tools/         the severance calculator and its rules per period
│   ├── privacy/       removing personal data; the 30-day question log
│   ├── service.py     what the app does, shared by the API and the screens
│   ├── api/           the HTTP API (FastAPI)
│   ├── ui/            the four screens (Gradio) and how answers are laid out
│   ├── evals/         the evaluation: runs, metrics, the automatic judge, the CI check
│   ├── cache.py       answer cache tied to the corpus, the model and the code
│   ├── env.py         settings from .env
│   └── cli.py         the `pasalkini` command
├── sources/           list of laws with official URLs and dates, manual events, topic words
├── evals/datasets/    78 dated test questions, and the same questions in other words
├── evals/runs/        one folder per evaluation run
├── tests/             about 500 tests, run on every push
├── docs/              results, architecture, how to add a new law, write-up
├── docker/            container files (not yet tested)
└── .github/workflows/ CI: lint, tests, retrieval check
```

## Results

Measured on 78 dated questions. The answer keys are drafts that a person still has to check, and the grading was done by AI, so these numbers are provisional.

| | Plain search-and-answer chatbot | PasalKini |
|---|---|---|
| Answers citing law that did not apply on the date | 65% (37 of 57) | 0% |
| Development questions answered fully right (read one by one) | 17 of 42 | 37 of 42 |
| Held-out questions answered right (automatic judge) | 11 of 36 | 26 of 36 |

Asked in other words, the questions do somewhat worse (34 of 42 and 25 of 36). Details, including what is still wrong, are in [docs/eval-results.md](docs/eval-results.md). These numbers are for the local Qwen model; Gemini has not been measured.

## Limits

- Not legal advice, and not checked by a lawyer yet.
- 12 instruments only; the new 2026 labor law is not in it yet.
- The text comes from scanned PDFs and can contain reading errors.
- A rule that was deleted is not always found unless the question names the article.
- The local model is small (4B) and sometimes misreads a passage it has in front of it.

## Data and privacy

- Sources: only official government publications ([peraturan.go.id](https://peraturan.go.id), [peraturan.bpk.go.id](https://peraturan.bpk.go.id), [mkri.id](https://www.mkri.id)). Indonesian laws and court decisions carry no copyright (UU 28/2014 Pasal 42).
- Personal data is removed before the search, the model or the log see a question. The log keeps no answers and is deleted after 30 days. The conversation is kept only in the browser tab.
- With the default local model nothing leaves the computer. With Gemini, the redacted question and the quoted law go to Google.

## More

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | How the parts fit, in more detail |
| [docs/eval-results.md](docs/eval-results.md) | All measurements and what each change did |
| [docs/runbook-new-instrument.md](docs/runbook-new-instrument.md) | How to add a new law or ruling |
| [CHANGELOG.md](CHANGELOG.md) | What changed, by date |
| [PLAN.md](PLAN.md) | The build plan, phase by phase |

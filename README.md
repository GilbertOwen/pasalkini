# PasalKini

Date-aware legal information assistant for Indonesian labor law.

Ask a labor-law question and a date. PasalKini answers with the law that applied **on that date**, cites the exact version of each article, and warns you if the rule has changed since.

> **Informasi hukum, bukan nasihat hukum.** PasalKini gives legal information generated with the help of AI. It is not legal advice and does not create a lawyer-client relationship. For a dispute or a deadline, contact the Dinas Ketenagakerjaan, your union, or a Lembaga Bantuan Hukum (LBH).

## Status

Phase 0 (setup) of the [build plan](PLAN.md). No answering pipeline yet.

## Why

Indonesian labor law has changed several times: UU 13/2003, the Cipta Kerja law (UU 11/2020, Perppu 2/2022, UU 6/2023), Constitutional Court decision 168/PUU-XXI/2023, and a new labor law in 2026. Standard retrieval-augmented generation retrieves the most *similar* text, not the version *in force*, so it can quote outdated law with confidence. PasalKini stores every version of every article with the dates it applied and filters by date before it searches.

## Quick start

```bash
uv sync
uv run pasalkini
uv run pytest
```

`uv run pasalkini` prints the state of the source manifest and the evaluation set.

## Layout

| Path | Contents |
|---|---|
| `sources/manifest.yaml` | Legal instruments in scope, with official URLs |
| `sources/topics.yaml` | Topics and the everyday words people use for them |
| `evals/datasets/golden.jsonl` | Dated test questions |
| `src/pasalkini/` | Package code |
| `tests/` | Tests |
| `PLAN.md` | Build plan, phases 0 to 9 |

## Data and compliance

- **Sources:** only official government publications: [peraturan.go.id](https://peraturan.go.id), the [BPK regulation database](https://peraturan.bpk.go.id) and [mkri.id](https://www.mkri.id). Laws, regulations and court decisions carry no copyright in Indonesia (UU 28/2014 Pasal 42).
- **Collection:** respects robots.txt, rate-limited, identified User-Agent, every document stored with its URL, retrieval date and checksum. No commercial legal databases are scraped.
- **Privacy:** development uses synthetic questions only. Any future public version redacts personal data before logging.
- **Models:** runs locally with Ollama by default.

Full legal review: [PasalKini: Project Brief and Legal Review](https://docs.google.com/document/d/1K8jFcSevIa8nTQAQv3emnZQDBh0L_d-MJR_yHxkwDcM/edit).

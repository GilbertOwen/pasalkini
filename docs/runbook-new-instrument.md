# Runbook: adding a legal instrument

Use this when a law, regulation or Constitutional Court (MK) ruling has to be added or replaced: the new labor law once it is promulgated, a new PP or Permenaker, an MK ruling on labor articles.

The order matters. Each step has a check; do not go on while a check fails.

```
manifest → download → parse → events → review → build → tests → calculator → index → questions → evals → fixture → app → release note
```

## Before you start

- **Promulgated text only.** The instrument must have a number and be published on an official site: [peraturan.go.id](https://peraturan.go.id), [peraturan.bpk.go.id](https://peraturan.bpk.go.id), a ministry JDIH page, or [mkri.id](https://www.mkri.id) for rulings. Never a draft, a news article or a commercial database.
- **Three dates**, read from the document itself: approved by the DPR (laws only), promulgated (for a ruling: pronounced), in force. Also note any article with its own later start date, and the transitional provisions.
- **Work on a branch.** An evaluation run loads the code on disk when it starts, so do not edit the checkout a run is using.

## 1. Manifest

Add an entry to `sources/manifest.yaml`. Copy an existing one of the same kind.

| Field | Notes |
|---|---|
| `id` | `uu-<number>-<year>`, `pp-…`, `permenaker-…`, `mk-<number>-puu-<roman>-<year>` |
| `status` | `active` once the fields below are filled; `pending` while the text is not out |
| `urls`, `pdf_url` | the official page and the PDF; `penjelasan_pdf_url` if the explanation is a separate file |
| `text_layer` | `typeset` or `ocr`. If two official sites serve different copies, take the one with fewer broken markers |
| `parse` | `scope_start` / `scope_end` to read one chapter only; `own_numbering: roman` for an amending regulation (Pasal I, Pasal II) |
| dates | from the document; leave `dates_verified: false` until a person has checked them against the PDF |
| `enacts` | only for a law that enacts a Perppu without changing its wording |

Check: `uv run pytest tests/test_sources.py`

## 2. Download

```bash
uv run pasalkini download --only <id>
```

One request every 3 seconds, robots.txt respected. The URL, size and SHA-256 go into `sources/downloads.lock.json`: commit that file.

Check: the result line says `downloaded`. `skipped` means robots.txt disallows the URL: use the other official site.

## 3. Parse

```bash
uv run pasalkini parse --only <id>   # quick look
uv run pasalkini parse               # all, and rewrites docs/parse-report.md
uv run pasalkini spotcheck           # docs/spot-check.md: random articles to compare with the PDFs
```

Check in `docs/parse-report.md`:

- the number of articles and the range (`1–193`) match the document;
- for an amending law, the amendment points are continuous (no gap in `angka`);
- the dates found in the closing match what you put in the manifest;
- the warnings are few and each one is understood.

Then compare at least ten articles of the new instrument with the PDF, including the longest and one with a table.

## 4. Events

```bash
uv run pasalkini build
```

This extracts every change as an event and replays all events by date into article versions. It rewrites `sources/events-review.csv` (keeping earlier verdicts), `data/processed/pasalkini.db` and `docs/temporal-report.md`.

What is extracted without help:

| In the document | Event |
|---|---|
| An article of a base law or regulation | `enact` on the in-force date |
| "Ketentuan Pasal X diubah sehingga berbunyi …" inside an amending article whose first sentence names the amended law | `amend` |
| "Di antara Pasal X dan Pasal Y disisipkan 1 (satu) pasal …" | `insert` |
| "Pasal X dihapus." | `delete` |
| An MK ruling point that names an article | `interpret` (the version becomes `conditional`) |

What you add by hand to `sources/events-manual.yaml`, each with the sentence it rests on:

| Situation | Event |
|---|---|
| The new instrument revokes a whole instrument ("dicabut dan dinyatakan tidak berlaku") | `revoke_instrument` |
| Implementing regulations stay "sepanjang tidak bertentangan" | `conditional_instrument` |
| Anything listed under Warnings in `docs/temporal-report.md` that is a real change | the matching event |

**If the new labor law replaces UU 13/2003** instead of amending it: add a `revoke_instrument` event for what it revokes, read its transitional provisions for what stays in force and until when, and expect every evaluation question dated after it to need new labels. Linking old articles to new ones (Pasal 59 of the old law to its successor) is not built yet; it is in `BACKLOG.md`.

## 5. Review the events

Open `sources/events-review.csv`, filter on the new instrument's `source_id`, and for each row set `review` to `verified` or `rejected` (say why in `comment`). Rejected events are left out of the next build. Run `uv run pasalkini build` again.

## 6. Check the temporal model

```bash
uv run pytest
uv run pasalkini history uu-13-2003/pasal-59 --diff      # a few articles the instrument changed
uv run pasalkini law <id> --date <its in-force date>
uv run pasalkini rulings                                 # for a new MK ruling
```

- The property tests must pass: versions of an article never overlap or leave a gap, and a later event never changes the law before its date.
- Each history you look at must match the documents: wording, dates, status.
- For an MK ruling, read each new line of `pasalkini rulings`. The readings are made by rule from the Court's fixed formulas (`src/pasalkini/temporal/rulings.py`); a formula it does not know is shown as written, and needs a rule and a test.

## 7. Calculator

Only if severance, long-service pay or PKWT compensation changed. Add a regime to `src/pasalkini/tools/rules/pesangon.yaml` with its dates, tables and the article each reason rests on, and add cases worked out by hand from the articles to `tests/test_pesangon.py`. Never take the expected amount from the calculator itself.

## 8. Index

```bash
uv run pasalkini index --config pasalkini
```

Needs Ollama. Only new or changed chunks are embedded; the rest come from the cache.

## 9. Evaluation questions

In `evals/datasets/golden.jsonl`:

- add questions about what changed, as pairs: the same question dated before and after the change, both in the same split;
- put some in `test`, and never tune on those;
- extend `must_not_cite` of existing questions whose date is after the change;
- re-check the questions dated "today";
- new keys are drafts: `source: draft`, `review: needed`, until a person has checked them (`evals/datasets/README.md`).

Check: `uv run pytest` (every label must match a chunk of the corpus).

## 10. Measure

```bash
uv run pasalkini eval pasalkini
uv run pasalkini compare <previous run> <new run>
```

- Stale citations must stay at 0%.
- Read the answers to the new development questions against their keys, and grade them.
- Held-out questions: totals only.

## 11. Retrieval fixture for CI

```bash
uv run pasalkini fixture
uv run pasalkini gate
```

Commit `evals/fixtures/retrieval.npz`. CI compares retrieval against this snapshot and fails if the snapshot no longer matches the answer keys.

## 12. App

Restart `uv run pasalkini serve`: the corpus is loaded at start. Cached answers are not reused: the corpus fingerprint is part of the cache key. `/health` shows the new fingerprint and the last day on which law in the corpus took effect.

## 13. Release note

Add an entry at the top of `CHANGELOG.md`: the instrument and its three dates, how many events and article versions it added, what was reviewed by a person and what was not, and the evaluation numbers before and after. Update the status line of `README.md` and `docs/eval-results.md` if the numbers moved.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| Article count is off by a few | OCR broke a marker; look at the warnings for that instrument in `docs/parse-report.md` |
| An amending article gives no events | Its first sentence does not name the amended law in the usual wording; see the warning in `docs/temporal-report.md` |
| A property test fails after the build | Two events on the same day in the wrong order: set `order` on the manual event (lower runs first) |
| `pytest` says a label matches no chunk | A question's source ID no longer exists in the corpus; fix the key, or the parse |
| The gate fails right after you changed questions | Expected: remake the fixture (step 11) |

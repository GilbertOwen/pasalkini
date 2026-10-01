# Changelog

What changed in the corpus and in the app, newest first. For a new legal instrument, follow `docs/runbook-new-instrument.md` and add an entry here.

## 2026-10-02: the app

- `uv run pasalkini serve`: an HTTP API and four screens (Tanya, Riwayat Pasal, Konsolidasi, Kalkulator Pesangon) on `http://127.0.0.1:8000`.
- Personal data (NIK, NPWP, phone numbers, e-mail, cued names) is taken out of a question before the search, the model, the log or a trace see it. The question log keeps no answers and is deleted after 30 days.
- A repeated question about the same date is answered from a cache that is tied to the corpus, the model settings and the code.
- `uv run pasalkini setup` goes from a fresh clone to a ready app; `uv run pasalkini gate` is the retrieval check that CI runs.
- Corpus unchanged: 12 instruments, 809 article versions, 848 chunks, fingerprint `03d906b40281a940`. The last change of law it holds took effect on 30 April 2026.

## 2026-10-01: answers checked for being right

- The answer is made in two checked steps, and code writes what it knows (an article's status, amounts, what an MK ruling changed). Development answers read against their keys: 33 to 36 of 42 fully correct, against 23 before and 17 for plain RAG. See `docs/eval-results.md`.

## 2026-09-30: first corpus

- UU 13/2003; UU 11/2020, Perppu 2/2022 and UU 6/2023 (Bab IV); PP 35/2021, PP 36/2021, PP 51/2023, PP 49/2025; Permenaker 7/2026; MK 19/PUU-IX/2011, MK 91/PUU-XVIII/2020, MK 168/PUU-XXI/2023.
- All dates read from the documents' closings by the parser; none checked by a person yet (`dates_verified: false`).

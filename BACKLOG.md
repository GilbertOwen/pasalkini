# Backlog

Ideas that are out of scope for the current phase. Move an item into PLAN.md only when a phase needs it.

- Add the older MK rulings on UU 13/2003 (on Pasal 158–160, 170, 171, 186, 96 and 153, listed on the BPK page) as instruments and interpret/annul events; until then the model shows those articles as in force until 2020.
- Record re-enactments with identical wording (Perppu 2/2022 restating UU 11/2020) so the history view can say "same wording"; OCR differences make a plain text comparison unreliable, so use a similarity threshold.
- Article lineage map (old article → new article) once the new labor law is promulgated, if it replaces UU 13/2003 rather than amending it.
- Add PP 78/2015 (the wage regulation before PP 36/2021) so minimum-wage questions dated before 2021 can be answered.
- Verify the Kepmen that limits long leave to "perusahaan tertentu" under UU 13/2003 Pasal 79 (possibly KEP.51/MEN/IV/2004) and add it to the manifest; istirahat-001-a depends on it.
- Convert document-level `expected_sources` for amended text (for example `uu-11-2020`) to point-level IDs (`uu-11-2020/pasal-81/angka-N`) once Phase 1 has parsed Pasal 81.
- Search alone still misses (Recall@5 0.73 to 0.77). The pipeline covers severance questions by always adding the articles that hold the severance tables; other topics have no such rule. Candidates: a reranker on the top 20 (`bge-reranker-v2-m3`, a 2 GB download), ayat-level chunks, or an LLM rewrite of the question into legal terms.
- When the two-step answer declines (2 of 36 held-out questions that the one-call answer of Phase 5 answered), try the one-call answer over the whole context as a last resort, with its quotes checked. Needs a look at whether those answers are right, which needs a person's grades on the held-out split.
- A larger local model for the answer step only. Two development answers are wrong with the right passage in front of the 4B model (long leave after 6 years; JKP read into "social security").
- Have a person review the plain readings of the 23 MK ruling points (`temporal/rulings.py`), in particular the one consequence code adds: striking the word "dapat" ends the choice.
- Page furniture inside parsed text: UU 13/2003 Pasal 66 as worded by Perppu 2/2022 carries "Dafam . . . SK No 137161 A" in ayat (3). The quote check tolerates it; the text shown to users does not.
- Why the same prompt can get a different answer from a server that has been running a while (docs/eval-results.md, section 6). Evaluation runs now start from a fresh model load; the app does not: its model stays loaded between questions, so a borderline question may be classified differently late in a long session.
- Questions written the way people write them. The evaluation questions are short and clean, and the development half was tuned on. Tried in the app on 2026-10-02:
  - a name and a phone number in front of a question sent the search to the wrong article (fixed: the question is redacted before the search);
  - "Berapa lama maksimal kontrak kerja waktu tertentu?" (2019): the model quoted Pasal 59 ayat (3) instead of ayat (4) and answered, with high confidence, that there is no maximum;
  - "Berapa lama masa percobaan untuk karyawan kontrak?" (2019): answered 3 months from Pasal 60, which is about permanent employment; Pasal 58 forbids probation in a fixed-term contract.

  A guard that withheld answers of the form "no rule exists" was tried and reverted (commit `5b1ea7f`): it made two development answers worse and fixed neither case above. Next: a robustness set of paraphrases, traps and chatty versions of the development questions, kept apart from the 78; then, measured against it, a rewrite of the question into a short legal query before the search, and letting the answer step read the whole of a short article it quoted from.
- Build and run the Docker files once Docker Desktop is installed (`docker/`), and look at a traced question in Phoenix (`PASALKINI_TRACE_ENDPOINT`).
- The app answers one question at a time and has no login or rate limit. Before any public hosting: the checklist in the legal review, a queue, limits per client.
- Join words the PDF extraction broke at a line end ("sebagai be-rikut", "sebagai-mana", "peru-bahan" in UU 13/2003). The citation check tolerates them; search and the text shown to users do not. Needs a re-parse and re-embedding.
- Timelines that say what changed between wordings. A re-enacted article gets a new wording with a new start date although its content is the same (Pasal 78 under UU 11/2020 and under Perppu 2/2022), and the model reports that date as the date of the change. A word-level diff per step would let code say "isi sama" or list the changed words; OCR noise in the Perppu text is the obstacle.
- Weekly law watch as a scheduled task: check peraturan.go.id for the promulgated new labor law and new labor PPs.
- Provincial minimum wage amounts (UMP/UMK) as a structured table.
- Labor rights set by other laws, for example maternity leave in UU 4/2024 on KIA.
- WhatsApp channel and voice input.

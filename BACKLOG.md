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

  A guard that withheld answers of the form "no rule exists" was tried and reverted (commit `5b1ea7f`): it made two development answers worse and fixed neither case above. Since then the 78 questions exist in a second wording (`evals/datasets/variants.jsonl`), and six changes were made from its development half (docs/eval-results.md, section 10). The second case above is fixed; the third is not in either set. What the reworded development questions still get wrong:
  - **A rule that was deleted, asked about without naming it** ("Bolehkah pengusaha yang tidak sanggup membayar upah minimum mengajukan penangguhan?", 2022). Only what applied on the date is searched, and what applied is the line "Pasal 90 dihapus.", which no question about suspension finds. The model then argues from the duty to pay wages on time, or declines. Idea: index a deleted article under its last wording, marked as deleted, and let code say when it was deleted, as it already does when the question is read as a status question.
  - **A tax question about severance is answered** ("Pesangon saya nanti kena potongan pajak berapa persen?": "at most 50%", from the limit on wage deductions). The original wording is refused. A keyword rule for tax would fix this one question and was not added.
  - **"Outsourcing"** finds no article on alih daya when the question is about what changed. `sources/topics.yaml` has the word; the history search does not use it well.
  - **Is the 2022 severance table a minimum?** flips between runs, in both wordings.
  - **JKP in 2019, original wording**: the model says the worker is entitled to it "as part of social security", adds that the law gives no details, and code, seeing "no rule", appends that the programme began in 2020. The two sentences contradict each other. The check for "no rule exists" should look at the answer's main claim, not at any sentence.
  - **A question's kind is misread.** 3 of 33 held-out rewordings were read as questions about an article's status. Since `4043424` that can no longer put an outdated wording among the sources, but the answer then opens with a status sentence nobody asked for. `pasalkini misread status` shows what such answers look like.
  - Tried and not kept: a rewrite of the question by the model before the search (Recall@5 0.62 to 0.63 on the reworded development questions), and the topic synonyms as extra rankings instead of extra words (no gain on either set).
- Build and run the Docker files once Docker Desktop is installed (`docker/`), and look at a traced question in Phoenix (`PASALKINI_TRACE_ENDPOINT`).
- The app answers one question at a time and has no login or rate limit. Before any public hosting: the checklist in the legal review, a queue, limits per client.
- Join words the PDF extraction broke at a line end ("sebagai be-rikut", "sebagai-mana", "peru-bahan" in UU 13/2003). The citation check tolerates them; search and the text shown to users do not. Needs a re-parse and re-embedding.
- Timelines that say what changed between wordings. A re-enacted article gets a new wording with a new start date although its content is the same (Pasal 78 under UU 11/2020 and under Perppu 2/2022), and the model reports that date as the date of the change. A word-level diff per step would let code say "isi sama" or list the changed words; OCR noise in the Perppu text is the obstacle.
- Weekly law watch as a scheduled task: check peraturan.go.id for the promulgated new labor law and new labor PPs.
- Provincial minimum wage amounts (UMP/UMK) as a structured table.
- Labor rights set by other laws, for example maternity leave in UU 4/2024 on KIA.
- WhatsApp channel and voice input.

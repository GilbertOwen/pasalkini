# Backlog

Ideas that are out of scope for the current phase. Move an item into PLAN.md only when a phase needs it.

- Add the older MK rulings on UU 13/2003 (on Pasal 158–160, 170, 171, 186, 96 and 153, listed on the BPK page) as instruments and interpret/annul events; until then the model shows those articles as in force until 2020.
- Record re-enactments with identical wording (Perppu 2/2022 restating UU 11/2020) so the history view can say "same wording"; OCR differences make a plain text comparison unreliable, so use a similarity threshold.
- Article lineage map (old article → new article) once the new labor law is promulgated, if it replaces UU 13/2003 rather than amending it.
- Add PP 78/2015 (the wage regulation before PP 36/2021) so minimum-wage questions dated before 2021 can be answered.
- Verify the Kepmen that limits long leave to "perusahaan tertentu" under UU 13/2003 Pasal 79 (possibly KEP.51/MEN/IV/2004) and add it to the manifest; istirahat-001-a depends on it.
- Convert document-level `expected_sources` for amended text (for example `uu-11-2020`) to point-level IDs (`uu-11-2020/pasal-81/angka-N`) once Phase 1 has parsed Pasal 81.
- Retrieval misses that hybrid search does not fix: pesangon-002 ("is the severance table a minimum?") never ranks Pasal 156, whose text is a long table. Candidates: a reranker on the top 20 (`bge-reranker-v2-m3`, a 2 GB download), ayat-level chunks, or an LLM rewrite of the question into legal terms.
- Use CPU embeddings in the application (Phase 7), as `ask` and the agent do now (`on_cpu=True`): the embedding model then stays loaded next to the chat model. The evaluation runner still embeds all questions on the GPU first and unloads the model.
- Join words the PDF extraction broke at a line end ("sebagai be-rikut", "sebagai-mana", "peru-bahan" in UU 13/2003). The citation check tolerates them; search and the text shown to users do not. Needs a re-parse and re-embedding.
- Timelines that say what changed between wordings. A re-enacted article gets a new wording with a new start date although its content is the same (Pasal 78 under UU 11/2020 and under Perppu 2/2022), and the model reports that date as the date of the change. A word-level diff per step would let code say "isi sama" or list the changed words; OCR noise in the Perppu text is the obstacle.
- Weekly law watch as a scheduled task: check peraturan.go.id for the promulgated new labor law and new labor PPs.
- Provincial minimum wage amounts (UMP/UMK) as a structured table.
- Labor rights set by other laws, for example maternity leave in UU 4/2024 on KIA.
- WhatsApp channel and voice input.

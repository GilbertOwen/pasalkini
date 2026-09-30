# Review notes for questions.jsonl (drafted 2026-09-30)

All 20 items now have `expected_sources` and `expected_points`. All `review` fields are still `"needed"` on purpose. These answer keys were drafted by an AI from secondary sources (hukumonline, MK summaries, news, and PDF copies of the regulations), not from a reading of the official gazette texts. Flip an item to `"done"` only after someone has checked it against the primary text.

## Dataset fixes applied (must_not_cite)

These were date errors: each source was issued after the item's `as_of` date and is relevant to the topic.

| id | as_of | added | why |
|---|---|---|---|
| pkwt-001-b | 2022-06-01 | perppu-2-2022 | Perppu issued 30 Dec 2022 |
| pesangon-001-b | 2022-06-01 | perppu-2-2022 | same |
| upah-001-a | 2022-06-01 | perppu-2-2022 | same |
| date-002 | 2022-01-15 | perppu-2-2022 | same |
| upah-001-b | 2024-06-01 | mk-168-puu-xxi-2023 | decision read 31 Oct 2024, changed wage rules |
| calc-001 | 2023-06-01 | mk-168-puu-xxi-2023 | restored "paling sedikit" in Pasal 156(2) |
| changed-001 | 2023-06-01 | mk-168-puu-xxi-2023 | reinterpreted Pasal 64(2) |

## Sources referenced in points but NOT added to expected_sources

I did not know whether these IDs exist in your manifest. They are mentioned in the answer points and should be added to the manifest (and then to `expected_sources`) if you want them graded:

- MK 91/PUU-XVIII/2020 (pkwt-001-b, date-002). Already in your BACKLOG.
- MK 19/PUU-IX/2011 (pesangon-001-a, date-001). It narrows Pasal 164(3) to permanent closure.
- The Kepmenakertrans on "perusahaan tertentu" for long leave (istirahat-001-a). This needs verification. My recollection is KEP.51/MEN/IV/2004, but I did not confirm it.
- Permenaker 7/2026 on Pekerjaan Alih Daya (status-002). It was announced 30 April 2026. It should also be added to `must_not_cite` for alih-daya items dated before that.
- pp-36-2021 is used in upah-001-a/b. I assumed it is in the manifest because the notes refer to it.

## Confidence per item

- pkwt-001-a, alih-daya-001-a, stable-001: [High]. These are long-standing rules of UU 13/2003. For stable-001, it is [Medium-high] that Cipta Kerja did not amend Pasal 60. Recent commentary cites Pasal 60 unamended, but I did not see the consolidated UU 6/2023 text.
- pkwt-001-b/c, date-002: [High] on the 5-year total including extension (PP 35/2021 Pasal 8; MK 168). Note that one hukumonline English summary wrongly describes this as "5 + another 5". I added a point that penalises that answer.
- alih-daya-001-b, changed-001, status-002: [High] that UU 11/2020 deleted Pasal 64 and 65 and Perppu 2/2022 reinserted Pasal 64. The earlier notes implied Pasal 64 was only amended, which is wrong. In changed-001, [Medium] on the claim that the 2003 automatic transfer of employment to the principal was not carried forward. Check the amended Pasal 66 wording.
- pesangon-001-a/b, calc-001: [High] on the multipliers (PP 35/2021 Pasal 40, 43, 44; UU 13/2003 Pasal 164(3)). The arithmetic in calc-001 is [High] given the inputs.
- date-001: [High] on 2x pesangon + 1x UPMK + UPH with 15%. [Medium] on how an answer should handle efficiency without closure after MK 19/2011. Practice varied, so the key asks the answer to flag it, not resolve it.
- istirahat-001-a: [Medium-high]. The "perusahaan tertentu" limitation is solid. The implementing Kepmen needs verification.
- istirahat-001-b: [High] (Kompas 2020 on the amended Pasal 79(5); PP 35/2021).
- upah-001-a/b: [High]. Formulas checked against PP 36/2021 and PP 51/2023 texts.
- status-001/002: [High] as of 30 Sept 2026, but these items expire soon. The DPR is targeting passage of the RUU Pelindungan Ketenagakerjaan on 6 to 8 October 2026, before the MK deadline of 31 October 2026. Re-check both items, and every item dated after the new law's effective date, once it is enacted.

## Structural issue

`expected_sources` uses document-level IDs only. If your grader expects article-level references (e.g. `uu-13-2003:pasal-59`), the articles are currently only in `expected_points`.

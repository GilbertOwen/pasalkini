"""Material for the human checks in Phase 1: dates found in closings, and a spot-check sheet."""

import json
import random
import re

from pasalkini.ingest.download import raw_path
from pasalkini.ingest.models import ParsedDocument
from pasalkini.paths import PROCESSED_DIR, ROOT

SPOT_CHECK_PATH = ROOT / "docs" / "spot-check.md"

DATE_IN_CLOSING = re.compile(
    r"(Disahkan|Ditetapkan|Diundangkan)\s+di\s+\w+\s+pada\s+tanggal\s+"
    r"(\d{1,2}|[\dOoIl]{1,2})\s+([A-Z][a-z]+)\s+([\dOoIl]{4})"
)


def closing_dates(doc: ParsedDocument) -> list[str]:
    """'Diundangkan: 30 Desember 2022' strings found in a law's closing, OCR digits repaired."""
    found = []
    for verb, day, month, year in DATE_IN_CLOSING.findall(doc.closing):
        fix = str.maketrans("OoIl", "0011")
        found.append(f"{verb}: {day.translate(fix)} {month} {year.translate(fix)}")
    if not found and doc.amar:
        spoken = re.search(r"diucapkan[^.]{0,220}", doc.closing, flags=re.I)
        if spoken:
            found.append(spoken.group().strip())
    return found


def load_docs() -> list[ParsedDocument]:
    return [
        ParsedDocument.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(PROCESSED_DIR.glob("*.json"))
    ]


def write_spot_check(n: int = 30, seed: int = 20260930) -> None:
    """A reproducible sample of articles, with where to find each one in the PDF."""
    rng = random.Random(seed)
    candidates = []  # (label for the sheet, pdf path, page, text)
    for doc in load_docs():
        pdf = raw_path(doc.instrument_id).relative_to(ROOT).as_posix()
        for article in doc.articles:
            if article.ayat or article.intro:
                title = f"{doc.instrument_id} {article.label}"
                candidates.append((title, pdf, article.page_start, article.full_text()))
            for point in article.points:
                for quoted in point.articles:
                    title = f"{point.source_id} (quoted {quoted.label})"
                    candidates.append((title, pdf, quoted.page_start, quoted.full_text()))
    sample = rng.sample(candidates, min(n, len(candidates)))

    out = [
        "# Spot check",
        "",
        f"{len(sample)} parsed articles picked at random (seed {seed}). For each, open the PDF at",
        "the page shown, compare the text, and tick the box if it matches. Note any difference",
        "below the item. OCR documents are expected to contain letter-level errors; what matters",
        "is that the article, its ayat and their order are right.",
        "",
    ]
    for k, (title, pdf, page, text) in enumerate(sample, start=1):
        excerpt = text if len(text) <= 900 else text[:900] + " …"
        out += [f"## {k}. {title}", "", f"- [ ] matches `{pdf}` page {page}", "", "```text"]
        out += [excerpt, "```", ""]
    SPOT_CHECK_PATH.write_text("\n".join(out), encoding="utf-8", newline="\n")

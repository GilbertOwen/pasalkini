"""Extract change events from the parsed documents and sources/events-manual.yaml.

- Articles of an instrument take effect on its in-force date ('enact').
- An amending article ('Beberapa ketentuan dalam Undang-Undang Nomor 13 Tahun 2003 … diubah
  sebagai berikut:') targets the law named in its first sentence; each amendment point becomes
  'amend' / 'insert' events for the articles it quotes, or 'delete' events ('Pasal 64 dihapus.').
- MK rulings become 'interpret' events on the articles they name, from the day they were read.
"""

import json
import re

import yaml

from pasalkini.ingest.models import Article, ParsedDocument
from pasalkini.paths import PROCESSED_DIR, SOURCES_DIR
from pasalkini.sources import Instrument, Kind, Manifest
from pasalkini.temporal.model import Event

MANUAL_EVENTS_PATH = SOURCES_DIR / "events-manual.yaml"

OCR_DIGITS = str.maketrans("OoIl", "0011")
TARGET_LAW = re.compile(
    r"(Undang-\s?Undang|Peraturan\s+Pemerintah)\s+Nomor\s+([\dOoIl]{1,4})\s+Tahun\s+([\dOoIl]{4})"
)
PASAL_REF = re.compile(r"Pasa[l1I]\s*([\dOoIl]+[A-Z]?)")
DELETE = re.compile(r"^(.*?)\s*dihapus\.?$")
# Inserting whole articles or sections. 'disisipkan 1 (satu) ayat' or 'ditambahkan 1 (satu) huruf'
# changes an existing article, so it is an amendment.
INSERT_WORDS = re.compile(
    r"(disisipkan|ditambahkan)\s+\d+\s*\(\w+\)\s*(pasal|bagian|bab|paragraf)", re.IGNORECASE
)
# 'Pasal 79 ayat (2) huruf b dalam Pasal 81 angka 25 Lampiran Undang-Undang Nomor 6 Tahun 2023'
MK_ON_CIPTA_KERJA = re.compile(
    r"Pasal\s+(\d+[A-Z]?)(?:\s+ayat\s+\(\w+\))?(?:\s+huruf\s+\w)?\s+dalam\s+Pasal\s+81\s+angka\s+\d+"
)
# 'Pasal 164 ayat (3) Undang-Undang Nomor 13 Tahun 2003'
MK_ON_LAW = re.compile(
    r"Pasal\s+(\d+[A-Z]?)(?:\s+ayat\s+\(\w+\))?\s+Undang-Undang\s+Nomor\s+(\d+)\s+Tahun\s+(\d{4})"
)


def provision_id(instrument_id: str, number: str) -> str:
    return f"{instrument_id}/pasal-{number.lower()}"


def normalise_number(token: str) -> str:
    digits = re.match(r"[\dOoIl]+", token).group()
    return digits.translate(OCR_DIGITS) + token[len(digits) :]


def target_instrument(article: Article) -> str | None:
    """The law an amending article changes, from its first sentence."""
    match = TARGET_LAW.search(article.intro)
    if not match:
        return None
    kind = "uu" if match.group(1).startswith("Undang") else "pp"
    number = match.group(2).translate(OCR_DIGITS)
    year = match.group(3).translate(OCR_DIGITS)
    return f"{kind}-{number}-{year}"


def events_from_regulation(
    doc: ParsedDocument, instrument: Instrument, known: set[str]
) -> tuple[list[Event], list]:
    """Events from a law or regulation. `known` holds the instruments whose text is in the corpus;
    an amendment to any other law is an insert, since there is no earlier wording to replace."""
    events: list[Event] = []
    warnings: list[str] = []
    day = instrument.in_force_on
    if day is None:
        return [], [f"{instrument.id}: no in-force date; skipped"]
    for article in doc.articles:
        if not article.points:
            events.append(
                Event(
                    id=f"{article.source_id}:enact",
                    op="enact",
                    effective_on=day,
                    source_id=article.source_id,
                    target=article.source_id,
                    label=article.label,
                    text=article.full_text(),
                )
            )
            continue
        target = target_instrument(article)
        if target is None:
            warnings.append(f"{article.source_id}: amended law not found in its first sentence")
            continue
        for point in article.points:
            instruction = point.instruction.strip()
            if point.articles:
                op = "insert" if INSERT_WORDS.search(instruction) else "amend"
                if target not in known:
                    op = "insert"
                for quoted in point.articles:
                    pid = provision_id(target, quoted.number)
                    events.append(
                        Event(
                            id=f"{point.source_id}:{op}:{pid}",
                            op=op,
                            effective_on=day,
                            source_id=point.source_id,
                            target=pid,
                            label=quoted.label,
                            text=quoted.full_text(),
                            note=instruction,
                        )
                    )
                continue
            deleted = DELETE.match(instruction.replace("\n", " "))
            numbers = PASAL_REF.findall(deleted.group(1)) if deleted else []
            if deleted and numbers and "ayat" not in deleted.group(1):
                for number in numbers:
                    pid = provision_id(target, normalise_number(number))
                    events.append(
                        Event(
                            id=f"{point.source_id}:delete:{pid}",
                            op="delete",
                            effective_on=day,
                            source_id=point.source_id,
                            target=pid,
                            label=f"Pasal {normalise_number(number)}",
                            note=instruction,
                        )
                    )
            else:
                warnings.append(
                    f"{point.source_id}: not an article change, ignored: {instruction[:70]}"
                )
    return events, warnings


def events_from_ruling(doc: ParsedDocument, instrument: Instrument) -> tuple[list[Event], list]:
    events: list[Event] = []
    warnings: list[str] = []
    day = instrument.in_force_on
    if day is None:
        return [], [f"{instrument.id}: no pronouncement date; skipped"]
    for point in doc.amar:
        text = point.text
        if "tidak dapat diterima" in text or not text.startswith("Menyatakan"):
            continue
        if "bertentangan" not in text and "kekuatan hukum mengikat" not in text:
            continue
        targets = [provision_id("uu-13-2003", n) for n in MK_ON_CIPTA_KERJA.findall(text)]
        targets += [provision_id(f"uu-{n}-{y}", a) for a, n, y in MK_ON_LAW.findall(text)]
        source_id = f"{instrument.id}/amar-{point.number}"
        if not targets:
            warnings.append(f"{source_id}: no article found in the ruling; not applied")
        for pid in dict.fromkeys(targets):
            events.append(
                Event(
                    id=f"{source_id}:interpret:{pid}",
                    op="interpret",
                    effective_on=day,
                    source_id=source_id,
                    target=pid,
                    note=text,
                    order=5,
                )
            )
    return events, warnings


def manual_events() -> list[Event]:
    data = yaml.safe_load(MANUAL_EVENTS_PATH.read_text(encoding="utf-8"))
    return [Event.model_validate(e) for e in data["events"]]


def extract_events(manifest: Manifest) -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    for instrument in manifest.instruments:
        path = PROCESSED_DIR / f"{instrument.id}.json"
        if instrument.status != "active" or not path.exists():
            continue
        doc = ParsedDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if instrument.kind is Kind.PUTUSAN_MK:
            found, notes = events_from_ruling(doc, instrument)
        else:
            found, notes = events_from_regulation(doc, instrument, manifest.ids())
        events += found
        warnings += notes
    events += manual_events()
    return events, warnings

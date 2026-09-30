"""Read the temporal model: an instrument as of a date, one article's history, and diffs."""

import difflib
import re
from datetime import date, timedelta

from pasalkini.temporal.model import Version

MONTHS_ID = [
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]


def format_date(day: date) -> str:
    return f"{day.day} {MONTHS_ID[day.month - 1]} {day.year}"


def article_sort_key(provision_id: str) -> tuple:
    """'uu-13-2003/pasal-61a' sorts after 'pasal-61' and before 'pasal-62'."""
    label = provision_id.rsplit("/pasal-", 1)[-1]
    match = re.match(r"(\d+)(.*)", label)
    return (int(match.group(1)), match.group(2)) if match else (10**6, label)


def consolidate(versions: list[Version], instrument_id: str, as_of: date) -> list[Version]:
    """The articles of an instrument as they stood on a date, in article order."""
    current = [
        v
        for v in versions
        if v.instrument_id == instrument_id and v.valid_on(as_of) and v.status != "repealed"
    ]
    return sorted(current, key=lambda v: article_sort_key(v.provision_id))


def history(versions: list[Version], provision_id: str) -> list[Version]:
    return sorted(
        (v for v in versions if v.provision_id == provision_id), key=lambda v: v.valid_from
    )


def word_diff(old: str, new: str) -> str:
    """Word-level diff: [-removed-] {+added+}."""
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(" ".join(a[i1:i2]))
        if op in ("delete", "replace"):
            out.append("[-" + " ".join(a[i1:i2]) + "-]")
        if op in ("insert", "replace"):
            out.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(out)


def validity(version: Version) -> str:
    """'berlaku 25 Maret 2003 s.d. 1 November 2020'. valid_to is exclusive: show the day before."""
    start = format_date(version.valid_from)
    if version.valid_to is None:
        return f"berlaku sejak {start}"
    return f"berlaku {start} s.d. {format_date(version.valid_to - timedelta(days=1))}"

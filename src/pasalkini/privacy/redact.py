"""Take personal data out of a question on its way in: before the search, the model, the question
log and the traces see it.

Each find is replaced by a placeholder that says what was there:

- e-mail addresses → [EMAIL]
- 16 digits in a row, or in four groups of four (NIK, family-card and card numbers) → [NIK]
- NPWP: 15 digits in a row, or written 12.345.678.9-012.345 → [NPWP]
- any longer run of digits (an NIP has 18) → [NOMOR]
- Indonesian phone numbers: mobile (+62 8…, 08…) and landline with an area code → [TELEPON]
- a name after 'nama saya', 'saya bernama' or 'atas nama', when it is capitalised → [NAMA]

Personal details are noise to the search as well as a risk in a log: a question that opened with a
name and a phone number retrieved the wrong article, and the same question without them the right
one. So the pipeline reads the redacted question too. That makes a false find costly: amounts of
money, dates and article numbers are what a question is about and must survive. The tests hold
the patterns to that, on examples and on every question of the evaluation set.

Not found: names written in lower case or without one of the cues above, addresses, account
numbers shorter than 15 digits. The app asks users not to enter personal data at all.
"""

import re
from dataclasses import dataclass

# No digit, letter or number punctuation just before: 'Rp10.812.345.678' and '2021-0812…' are not
# phone numbers.
NOT_INSIDE = r"(?<![\w.,/-])"

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DIGIT_RUN = re.compile(r"(?<!\d)\d{15,}(?!\d)")
NIK_GROUPED = re.compile(r"(?<![\d.,-])\d{4}(?:[ .-]\d{4}){3}(?![\d.,-]\d)")
NPWP_WRITTEN = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}(?!\d)")
# After the country code or the leading 0, every mobile number starts with 8. The groups are of
# three or four digits, so '08-12-2021 10.00' (a date and a time) is not taken for a number.
MOBILE = re.compile(NOT_INSIDE + r"(?:\+62|62|0)[ .-]?8\d{1,2}(?:[ .-]?\d{3,4}){2,3}(?!\d)")
LANDLINE = re.compile(NOT_INSIDE + r"\(?0\d{2,3}\)?[ .-]\d{3,4}[ .-]?\d{3,4}(?!\d)")
# The cue in any case, the name itself capitalised: 'nama saya tidak tercantum' has no name.
NAME = re.compile(
    r"\b((?i:nama(?: lengkap)? saya|saya bernama|atas nama|a\.n\.)\s+(?:(?i:adalah)\s+)?)"
    r"([A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,3})"
)


@dataclass(frozen=True)
class Redacted:
    text: str
    found: dict[str, int]  # what was replaced and how often: {'telepon': 1}

    @property
    def clean(self) -> bool:
        return not self.found


def redact(text: str) -> Redacted:
    found: dict[str, int] = {}

    def swap(pattern: re.Pattern, kind: str, text: str) -> str:
        text, count = pattern.subn(f"[{kind.upper()}]", text)
        if count:
            found[kind] = found.get(kind, 0) + count
        return text

    def long_number(match: re.Match) -> str:
        kind = {15: "npwp", 16: "nik"}.get(len(match.group()), "nomor")
        found[kind] = found.get(kind, 0) + 1
        return f"[{kind.upper()}]"

    def name(match: re.Match) -> str:
        found["nama"] = found.get("nama", 0) + 1
        return match.group(1) + "[NAMA]"

    text = swap(EMAIL, "email", text)
    text = swap(NPWP_WRITTEN, "npwp", text)
    text = DIGIT_RUN.sub(long_number, text)
    text = swap(NIK_GROUPED, "nik", text)
    text = swap(MOBILE, "telepon", text)
    text = swap(LANDLINE, "telepon", text)
    text = NAME.sub(name, text)
    return Redacted(text, found)

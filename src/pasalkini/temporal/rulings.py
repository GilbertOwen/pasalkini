"""Constitutional Court rulings in fewer words.

A ruling point (amar) is one long sentence, and most of it is citation: the full title of the
law, its gazette numbers, the constitution's full name. Two helpers:

- abbreviate(): the same sentence with those citations in short form ('UU 6/2023', 'UUD 1945').
  The words that say what the Court decided are not touched.
- reading(): what the ruling means for the article, from the Court's fixed formulas.
  '... bertentangan dengan UUD 1945 dan tidak memiliki kekuatan hukum mengikat sepanjang tidak
  dimaknai "Y"' leaves the provision in force, read as Y. Without 'sepanjang', the provision no
  longer applies. A sentence that fits neither formula is returned abbreviated, not interpreted
  (MK 91/PUU-XVIII/2020 on the making of UU 11/2020, 'secara bersyarat', is one).
"""

import re

SHORT_FORMS = [
    (
        re.compile(
            r"\s*\(Lembaran Negara Republik Indonesia Tahun \d{4} Nomor \d+, Tambahan Lembaran "
            r"Negara Republik Indonesia Nomor \d+\)"
        ),
        "",
    ),
    (
        re.compile(
            r"Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti "
            r"Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja Menjadi Undang-Undang"
        ),
        "UU 6/2023",
    ),
    (
        re.compile(
            r"Undang-Undang Nomor (\d+) Tahun (\d{4}) tentang (?:Ketenagakerjaan|Cipta Kerja)"
        ),
        r"UU \1/\2",
    ),
    (re.compile(r"Undang-Undang Dasar Negara Republik Indonesia Tahun 1945"), "UUD 1945"),
]
NOT_BINDING = r"tidak (?:memiliki|mempunyai) kekuatan hukum mengikat"
FORMULA = re.compile(
    r"^Menyatakan (?P<subject>.+?),? "
    rf"(?:bertentangan dengan UUD 1945(?: dan {NOT_BINDING})?|{NOT_BINDING})"
    r",?"
    r"(?: sepanjang (?P<phrase>frasa “[^”]+” )?tidak dimaknai(?P<covers> mencakup frasa)?,? "
    r"(?P<meaning>.+?))?[;.]?$",
    re.DOTALL,
)
# 'Pasal 79 ayat (5) dalam Pasal 81 angka 25 Lampiran UU 6/2023': the second half says where the
# amended wording was published, which the reader of that wording already knows.
PUBLISHED_IN = re.compile(r",? dalam Pasal 81 angka \d+ Lampiran UU 6/2023")
AYAT_OF = re.compile(r"Pasal \d+[A-Z]? ayat \((\d+)\)")


def abbreviate(text: str) -> str:
    for pattern, short in SHORT_FORMS:
        text = pattern.sub(short, text)
    return text


def ayat_of(text: str) -> str | None:
    """The ayat a ruling point is about ('2' for 'Pasal 79 ayat (2) huruf b'), if it names one."""
    match = AYAT_OF.search(text)
    return match.group(1) if match else None


def meaning_of(text: str) -> str | None:
    """The reading the Court set ('“paling sedikit”'), for conditional rulings."""
    match = FORMULA.match(abbreviate(" ".join(text.split())))
    return match["meaning"].strip() if match and match["meaning"] else None


def reading(text: str, court: str) -> str:
    """One sentence on what the ruling point does. `court` names the ruling:
    'Putusan MK 168/PUU-XXI/2023'."""
    short = abbreviate(" ".join(text.split()))
    match = FORMULA.match(short)
    if match is None:
        return f"{court}: {short}"
    subject = PUBLISHED_IN.sub("", match["subject"]).strip().rstrip(",")
    subject = subject.replace("”, dalam", "” dalam")
    if match["phrase"]:
        subject = f"{match['phrase'].strip()} dalam {subject}"
    if match["meaning"]:
        how = "dimaknai mencakup frasa" if match["covers"] else "dimaknai"
        return f"Menurut {court}, {subject} hanya berlaku jika {how} {match['meaning'].strip()}."
    sentence = (
        f"Menurut {court}, {subject} tidak berlaku lagi (tidak mempunyai kekuatan hukum mengikat)"
    )
    if subject.startswith(("kata ", "frasa ")):
        sentence += ": baca ketentuan itu tanpa kata-kata tersebut"
    return sentence + "."

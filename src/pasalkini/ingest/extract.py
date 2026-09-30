"""PDF → clean lines with page numbers.

Removes what repeats on every page and is not part of the legal text:
- running headers: 'PRESIDEN' / 'REPUBLIK INDONESIA' (also OCR variants such as 'PRESIDEi{'),
  Lembaran Negara headers such as '2021, No.45', and 'SALINAN';
- page numbers such as '- 21 -' or '-9-';
- 'SK No 031791 A' stamps on scanned copies;
- catchwords: the last line of a page that repeats the first words of the next page and ends
  in dots, such as '(3) Perjanjian ...'.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

HEADER_LINES = 4  # running headers only occur in the first few lines of a page

HEADER_PATTERNS = [
    re.compile(r"^PRES\s?[I1l]\s?DE\S{0,3}$"),  # also OCR 'PRES IDEN'
    re.compile(r"^REP\S{2,5}K\s+[I1l]NDONES[I1l]A$"),  # also OCR 'REP1JBLIK INDONESIA'
    re.compile(r"^\d{4},\s*No\.\s*\d+$"),
    re.compile(r"^SALINAN$"),
]
PAGE_NUMBER = re.compile(r"^-\s*[\dIlOoSt]{1,4}\s*-$")
STAMP = re.compile(r"^SK\s*No\.?\s*[\dO][\dO ]*\s*[A-Z]?$")
# Footers printed on every page of JDIH Kemnaker copies
FOOTERS = [
    re.compile(r"^jdih\.kemnaker\.go\.id$"),
    re.compile(r"^Dokumen ini telah ditandatangani secara elektronik"),
]
CATCHWORD = re.compile(r"^.{1,45}?(\s?\.){2,}\s*$|^.{1,45}…\s*$")


@dataclass(frozen=True)
class Line:
    page: int  # 1-based page number in the PDF
    text: str


def clean_page(text: str, page_number: int | None = None) -> list[str]:
    text = text.replace("www.peraturan.go.id", "")  # footer on peraturan.go.id copies
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    kept = []
    for i, ln in enumerate(lines):
        if i < HEADER_LINES and any(p.match(ln) for p in HEADER_PATTERNS):
            continue
        if i < HEADER_LINES and page_number is not None and ln == str(page_number):
            continue  # bare page number, as in older MK decisions
        if PAGE_NUMBER.match(ln) or STAMP.match(ln) or any(f.match(ln) for f in FOOTERS):
            continue
        kept.append(ln)
    if kept and CATCHWORD.match(kept[-1]):
        kept.pop()
    return kept


def extract_lines(pdf_path: Path) -> list[Line]:
    doc = pymupdf.open(pdf_path)
    try:
        return [
            Line(page_number, text)
            for page_number, page in enumerate(doc, start=1)
            for text in clean_page(page.get_text("text"), page_number)
        ]
    finally:
        doc.close()

"""Output models of the Phase 1 parser, written to data/processed/<instrument>.json."""

from pydantic import BaseModel


class Ayat(BaseModel):
    number: str  # "1", "1a"
    text: str


class EmbeddedArticle(BaseModel):
    """An article quoted inside an amendment point: the new wording of another law's article."""

    label: str  # "Pasal 59"
    number: str  # "59", "61A"
    intro: str = ""  # text before the first ayat, or the whole text when there are no ayat
    ayat: list[Ayat] = []
    page_start: int
    page_end: int

    def full_text(self) -> str:
        return render(self.intro, self.ayat)


class AmendmentPoint(BaseModel):
    """One numbered point ('angka') of an amending article, e.g. Pasal 81 angka 15."""

    source_id: str  # 'uu-11-2020/pasal-81/angka-15'
    number: int
    number_inferred: bool = False  # true when OCR lost the number and the parser inferred it
    instruction: str  # 'Ketentuan Pasal 59 diubah sehingga berbunyi sebagai berikut:'
    articles: list[EmbeddedArticle] = []
    page_start: int
    page_end: int


class Article(BaseModel):
    source_id: str  # 'uu-13-2003/pasal-59'
    label: str
    number: str
    context: dict[str, str] = {}  # bab, bab_title, bagian, bagian_title, paragraf, paragraf_title
    intro: str = ""
    ayat: list[Ayat] = []
    points: list[AmendmentPoint] = []
    penjelasan: str | None = None
    page_start: int
    page_end: int

    def full_text(self) -> str:
        return render(self.intro, self.ayat)


class AmarPoint(BaseModel):
    number: int
    text: str


class ParsedDocument(BaseModel):
    instrument_id: str
    text_layer: str
    files: dict[str, str]  # part -> sha256 of the PDF it was parsed from
    scope: str | None = None
    articles: list[Article] = []
    penjelasan_umum: str | None = None
    amar: list[AmarPoint] = []
    closing: str = ""
    warnings: list[str] = []


def render(intro: str, ayat: list[Ayat]) -> str:
    parts = [intro] if intro else []
    parts += [f"({a.number}) {a.text}" for a in ayat]
    return "\n".join(parts)

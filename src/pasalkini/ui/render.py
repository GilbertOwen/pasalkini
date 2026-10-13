"""What the screens show, as HTML built from the service's answers.

Legal text is never passed through Markdown: a line that starts with '3.' would be renumbered as
a list item. It is escaped and shown with its own line breaks. Everything that comes from a
question, the model or a document is escaped.
"""

import html
from datetime import date

from pasalkini.answer.pipeline import EARLIER_HEADING
from pasalkini.temporal.query import diff_segments, format_date

DISCLAIMER = (
    "Informasi hukum, bukan nasihat hukum. Jawaban disusun dengan bantuan AI dari teks peraturan "
    "dan dapat keliru: periksa kutipan sumbernya."
)
INTENT_WORDS = {
    "explain": "penjelasan aturan",
    "status": "status pasal",
    "history": "perubahan aturan",
    "calculate": "hitungan",
    "out_of_scope": "di luar cakupan",
}
CONFIDENCE_WORDS = {"high": "tinggi", "medium": "sedang", "low": "rendah"}
STATUS_BADGES = {"conditional": "berlaku bersyarat", "repealed": "dihapus"}


def esc(text: object) -> str:
    return html.escape(str(text))


def legal(text: str) -> str:
    return f'<div class="pk-legal">{esc(text)}</div>'


def record(text: str) -> str:
    """Text written by code (a timeline, a calculation): kept apart from the law's own words,
    which are set in a serif."""
    return f'<div class="pk-record">{esc(text)}</div>'


def notice(text: str) -> str:
    return f'<div class="pk-notice">{esc(text)}</div>'


def source_code(source_id: str) -> str:
    return f'<code class="pk-id">{esc(source_id)}</code>'


def rupiah(amount: int | None) -> str:
    return "–" if amount is None else "Rp" + f"{amount:,}".replace(",", ".")


def day_text(iso: str | None) -> str:
    return format_date(date.fromisoformat(iso)) if iso else ""


def items(lines: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(line.removeprefix('- '))}</li>" for line in lines) + "</ul>"


def passages(title: str, found: list[dict], role: str = "source") -> str:
    """Quoted legal text under a heading. `role` marks how it relates to the date asked about:
    source (applied on it), nearest (found, not answering), earlier (had ended), later (began
    after it)."""
    if not found:
        return ""
    rows = "".join(
        f'<li><span class="pk-source">{esc(p["title"])}</span> '
        f'<code class="pk-id">{esc(p["source_id"])}</code>'
        f"<blockquote>{esc(p['quote'])}</blockquote></li>"
        for p in found
    )
    return (
        f'<section class="pk-group pk-{role}"><h4>{esc(title)}</h4>'
        f'<ul class="pk-passages">{rows}</ul></section>'
    )


def answer_html(payload: dict) -> str:
    """One answer: what was asked about which date, the answer, and everything it rests on."""
    parts = []
    if payload["looked_up"]:  # a refusal looks nothing up, so it has no date to state
        day, _, source = payload["as_of_text"].partition(" (")
        parts.append(
            '<div class="pk-asof"><span class="pk-asof-lead">Menurut hukum yang berlaku pada'
            f'</span> <span class="pk-date">{esc(day)}</span>'
            f' <span class="pk-asof-source">({esc(source)}</span></div>'
        )
    parts.append(f'<div class="pk-said">{esc(payload["answer"])}</div>')
    if payload["calculation"]:
        parts.append("<h4>Hitungan (oleh program)</h4>" + record(payload["calculation"]["text"]))
    if payload["timeline"]:
        parts.append("<h4>Riwayat (oleh program)</h4>" + record(payload["timeline"]))
    parts.append(passages("Sumber", payload["citations"]))
    parts.append(passages("Kutipan terdekat yang ditemukan", payload["nearest"], "nearest"))
    parts.append(passages(EARLIER_HEADING, payload["earlier"], "earlier"))
    parts.append(passages("Aturan yang berlaku kemudian", payload["later"], "later"))
    if payload["changed_since"]:
        parts.append("<h4>Perubahan sesudah tanggal itu</h4>" + items(payload["changed_since"]))
    if payload["caveats"]:
        parts.append("<h4>Catatan</h4>" + items(payload["caveats"]))
    if payload["referral"]:
        also = "" if payload["abstained"] else "juga "
        parts.append(
            f'<p class="pk-referral">Sebaiknya tanyakan {also}ke: {esc(payload["referral"])}</p>'
        )
    facts = [f"Jenis pertanyaan: {INTENT_WORDS.get(payload['intent'], payload['intent'])}."]
    if not payload["abstained"]:
        confidence = CONFIDENCE_WORDS.get(payload["confidence"], payload["confidence"])
        facts.insert(0, f"Keyakinan: {confidence}.")
    if payload["cached"]:
        facts.append("Jawaban yang sama sudah pernah diberikan (dari simpanan).")
    else:
        seconds = f"{payload['seconds'].get('total', 0):.1f}".replace(".", ",")
        facts.append(f"Dijawab dalam {seconds} detik.")
    parts.append(f'<div class="pk-meta">{esc(" ".join(facts))}</div>')
    parts.append(f'<div class="pk-meta">{esc(DISCLAIMER)}</div>')
    return '<div class="pk-answer">' + "".join(parts) + "</div>"


def provision_html(found: dict | None) -> str:
    """One article as it stood on a date, with what the Constitutional Court ruled about it."""
    if found is None:
        return notice("Pasal ini tidak ada dalam sumber PasalKini.")
    if not found["exists_on_date"]:
        return notice(found["message"])
    badge = STATUS_BADGES.get(found["status"])
    head = f"<h4>{esc(found['title'])}"
    head += f' <span class="pk-badge">{esc(badge)}</span></h4>' if badge else "</h4>"
    parts = [
        head,
        f'<div class="pk-meta">Bunyi dari {esc(found["published_in"])} '
        f'<code class="pk-id">{esc(found["source_id"])}</code>, menurut keadaan pada '
        f"{esc(day_text(found['as_of']))}</div>",
        legal(found["text"]),
    ]
    if found["rulings_read"]:
        parts.append("<h4>Putusan Mahkamah Konstitusi atas bunyi ini</h4>")
        parts.append(items(found["rulings_read"]))
    other = [note["text"] for note in found["notes"] if "/amar-" not in note["id"]]
    if other:
        parts.append("<h4>Catatan</h4>" + items(other))
    return '<div class="pk-article">' + "".join(parts) + "</div>"


def diff_html(old: str, new: str) -> str:
    """Word-level changes: removed words struck through, added words underlined."""
    marks = {"-": "<del>{}</del>", "+": "<ins>{}</ins>", None: "{}"}
    words = " ".join(marks[kind].format(esc(text)) for text, kind in diff_segments(old, new))
    return f'<div class="pk-legal pk-diff">{words}</div>'


def version_label(number: int, version: dict) -> str:
    """'2. berlaku 2 November 2020 s.d. 29 Desember 2022 · UU 11/2020 · bersyarat'."""
    parts = [f"{number}. {version['validity']}", version["published_in"]]
    if version["status"] in STATUS_BADGES:
        parts.append(STATUS_BADGES[version["status"]])
    return " · ".join(parts)


def history_html(found: dict | None) -> str:
    """An article's timeline as code states it, then every version in full."""
    if found is None:
        return notice("Pasal ini tidak ada dalam sumber PasalKini.")
    parts = [f"<h3>{esc(found['label'])}</h3>"]
    if found["timeline"]:
        parts.append(record(found["timeline"]))
    for number, version in enumerate(found["versions"], start=1):
        parts.append(f"<h4>{esc(version_label(number, version))}</h4>")
        parts.append(f'<div class="pk-meta">{source_code(version["source_id"])}</div>')
        if version["same_text_as_previous"]:
            parts.append(
                '<div class="pk-meta">Bunyi sama dengan versi sebelumnya; yang berubah adalah '
                "statusnya.</div>"
            )
        else:
            parts.append(legal(version["text"]))
        if version["notes"]:
            parts.append('<div class="pk-meta">Catatan pada versi ini:</div>')
            parts.append(items(version["notes"]))
    return '<div class="pk-article">' + "".join(parts) + "</div>"


def law_html(found: dict | None) -> str:
    """A law as it stood on a date, article by article."""
    if found is None:
        return notice("Peraturan ini tidak ada dalam sumber PasalKini.")
    articles = found["articles"]
    day = day_text(found["as_of"])
    if not articles:
        return notice(f"Tidak ada pasal {found['name']} yang berlaku pada {day} sesuai pilihan.")
    amended = sum(a["amended"] for a in articles)
    conditional = sum(a["status"] == "conditional" for a in articles)
    summary = f"{found['name']} menurut bunyi yang berlaku pada {day}: {len(articles)} pasal"
    if amended:
        summary += f", {amended} di antaranya dengan bunyi dari peraturan lain"
    if conditional:
        summary += f", {conditional} berlaku bersyarat"
    parts = [f'<div class="pk-asof">{esc(summary)}.</div>']
    for article in articles:
        badge = STATUS_BADGES.get(article["status"])
        head = f"<h4>{esc(article['label'])}"
        head += f' <span class="pk-badge">{esc(badge)}</span></h4>' if badge else "</h4>"
        parts.append(head)
        parts.append(
            f'<div class="pk-meta">{esc(article["validity"])}; bunyi dari '
            f'<code class="pk-id">{esc(article["source_id"])}</code></div>'
        )
        parts.append(legal(article["text"]))
    return '<div class="pk-article">' + "".join(parts) + "</div>"


def calculation_html(result: dict, wage: int | None) -> str:
    """A calculator result: one row per component with its formula and legal basis."""
    if result["unsupported"]:
        return notice(result["unsupported"])
    titles = {source["source_id"]: source["title"] for source in result["sources"]}
    rows = "".join(
        f"<tr><td>{esc(line['component'])}</td><td>{esc(line['formula'])}</td>"
        f'<td class="pk-amount">{esc(rupiah(line["amount"]))}</td>'
        f"<td>{esc('; '.join(titles.get(b, b).split(' (')[0] for b in line['basis']))}</td></tr>"
        for line in result["lines"]
    )
    parts = [
        f'<div class="pk-asof">Aturan yang dipakai: {esc(result["regime"])}; masa kerja: '
        f"{esc(result['service'])}; upah sebulan: {esc(rupiah(wage))}.</div>"
    ]
    if result["reason"]:
        parts.append(f'<div class="pk-meta">Alasan PHK: {esc(result["reason"])}</div>')
    if rows:
        parts.append(
            '<table class="pk-table"><thead><tr><th>Komponen</th><th>Rumus</th><th>Jumlah</th>'
            f"<th>Dasar hukum</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    least = "paling sedikit " if result["minimum"] else ""
    if result["total"] is not None:
        total = esc(rupiah(result["total"]))
        parts.append(f'<div class="pk-said">Jumlah yang dapat dihitung: {least}{total}</div>')
    elif result["total_months_of_wage"]:
        months = f"{result['total_months_of_wage']:g}".replace(".", ",")
        parts.append(f'<div class="pk-said">Jumlah: {least}{esc(months)} bulan upah</div>')
    if result["other_reasons_same_article"]:
        parts.append("<h4>Alasan lain dalam pasal yang sama</h4>")
        parts.append(items(result["other_reasons_same_article"]))
    if result["notes"]:
        parts.append("<h4>Catatan</h4>" + items(result["notes"]))
    parts.append(
        '<div class="pk-meta">Dihitung oleh program dari aturan yang berlaku pada '
        f"{esc(day_text(result['as_of']))}, bukan oleh AI. Periksa juga perjanjian kerja, "
        "peraturan perusahaan dan perjanjian kerja bersama Anda.</div>"
    )
    return '<div class="pk-answer">' + "".join(parts) + "</div>"

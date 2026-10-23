"""What the screens show, as HTML built from the service's answers.

Legal text is never passed through Markdown: a line that starts with '3.' would be renumbered as
a list item. It is escaped and shown with its own line breaks. Everything that comes from a
question, the model or a document is escaped.
"""

import html
import re
from datetime import date

from pasalkini.answer.context import instrument_label
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


def badge(status: str) -> str:
    """An article's status, in its colour. Nothing for an article simply in force."""
    word = STATUS_BADGES.get(status)
    return f' <span class="pk-badge pk-{esc(status)}">{esc(word)}</span>' if word else ""


ID_IN_TEXT = re.compile(r"\s*\[([^\]\s]+)\]")


def timeline_html(text: str) -> str:
    """A timeline as code writes it ('- 25 Maret 2003 s.d. 1 November 2020: bunyi asli [id]',
    then 'Pada …: …'), as a list of periods: when, what, and the source ID set apart."""
    blocks = []
    for chunk in text.strip().split("\n\n"):
        rows, closing = [], []
        for line in chunk.splitlines():
            ids = " ".join(source_code(found) for found in ID_IN_TEXT.findall(line))
            plain = ID_IN_TEXT.sub("", line)
            if plain.startswith("- "):
                when, _, what = plain[2:].partition(": ")
                rows.append(
                    f'<li><span class="pk-when">{esc(when)}</span>'
                    f'<span class="pk-what">{esc(what)} {ids}</span></li>'
                )
            elif plain.startswith("Riwayat ") and plain.endswith(":"):
                continue  # the article's name: the heading above says it
            else:
                closing.append(f'<p class="pk-now">{esc(plain)} {ids}</p>')
        blocks.append(f'<ol class="pk-periods">{"".join(rows)}</ol>{"".join(closing)}')
    return '<div class="pk-timeline">' + "".join(blocks) + "</div>"


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
    heading = f"<h4>{esc(title)}</h4>" if title else ""
    rows = "".join(
        f'<li><span class="pk-source">{esc(p["title"])}</span> '
        f'<code class="pk-id">{esc(p["source_id"])}</code>'
        f"<blockquote>{esc(p['quote'])}</blockquote></li>"
        for p in found
    )
    return (
        f'<section class="pk-group pk-{role}">{heading}'
        f'<ul class="pk-passages">{rows}</ul></section>'
    )


def answer_html(payload: dict) -> str:
    """One answer, in the order a reader needs it: the date it is for, the answer, the law it
    rests on, then what changed later. The longer record (the article's timeline, earlier
    wordings) is folded, and the small print comes last."""
    parts = []
    if payload["looked_up"]:  # a refusal looks nothing up, so it has no date to state
        day, _, source = payload["as_of_text"].partition(" (")
        parts.append(
            '<div class="pk-asof"><span class="pk-asof-lead">Menurut hukum yang berlaku pada'
            f'</span> <span class="pk-date">{esc(day)}</span>'
            f' <span class="pk-asof-source">({esc(source)}</span></div>'
        )
    if payload.get("asked_as"):
        parts.append(f'<p class="pk-asked">Dibaca sebagai: “{esc(payload["asked_as"])}”</p>')
    parts.append(f'<div class="pk-said">{esc(payload["answer"])}</div>')
    if payload["calculation"]:
        parts.append("<h4>Hitungan (oleh program)</h4>" + record(payload["calculation"]["text"]))
    parts.append(passages("Sumber", payload["citations"]))
    parts.append(passages("Kutipan terdekat yang ditemukan", payload["nearest"], "nearest"))
    parts.append(passages("Aturan yang berlaku kemudian", payload["later"], "later"))
    if payload["changed_since"]:
        parts.append(
            '<section class="pk-changed"><h4>Perubahan sesudah tanggal itu</h4>'
            + items(payload["changed_since"])
            + "</section>"
        )
    if payload["timeline"]:
        parts.append(folded("Riwayat pasal (oleh program)", timeline_html(payload["timeline"])))
    if payload["earlier"]:
        parts.append(folded(EARLIER_HEADING, passages("", payload["earlier"], "earlier")))
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
    if payload.get("answered_by"):
        facts.append(f"Ditulis oleh model {payload['answered_by']}.")
    parts.append(
        f'<footer class="pk-small"><p>{esc(" ".join(facts))}</p><p>{esc(DISCLAIMER)}</p></footer>'
    )
    return '<div class="pk-answer">' + "".join(parts) + "</div>"


def question_html(typed: str) -> str:
    """What the asker typed, as their side of the conversation."""
    return f'<div class="pk-you">{esc(typed)}</div>' if typed else ""


def conversation_html(entries: list[dict]) -> str:
    """Earlier turns, oldest first: each question with its answer in short (the date it was
    for and the answer's sentences). The sources stay with the newest answer."""
    if not entries:
        return ""
    turns = []
    for entry in entries:
        payload = entry["payload"]
        day = payload["as_of_text"].partition(" (")[0] if payload["looked_up"] else ""
        asked = payload.get("asked_as")
        turns.append(
            '<div class="pk-turn">'
            + question_html(entry["typed"])
            + (f'<p class="pk-asked">Dibaca sebagai: “{esc(asked)}”</p>' if asked else "")
            + (f'<p class="pk-turn-date">Menurut hukum pada {esc(day)}</p>' if day else "")
            + f'<div class="pk-turn-said">{esc(payload["answer"])}</div></div>'
        )
    return '<div class="pk-conversation">' + "".join(turns) + "</div>"


def folded(title: str, body: str) -> str:
    """A section closed until the reader opens it."""
    return f'<details class="pk-fold"><summary>{esc(title)}</summary>{body}</details>'


def provision_html(found: dict | None) -> str:
    """One article as it stood on a date, with what the Constitutional Court ruled about it."""
    if found is None:
        return notice("Pasal ini tidak ada dalam sumber PasalKini.")
    if not found["exists_on_date"]:
        return notice(found["message"])
    parts = [
        f"<h4>{esc(found['title'])}{badge(found['status'])}</h4>",
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
    return (
        '<p class="pk-meta">Dicoret: dihapus dari versi lama. Digarisbawahi: ditambahkan di '
        f'versi baru.</p><div class="pk-legal pk-diff">{words}</div>'
    )


def version_label(number: int, version: dict) -> str:
    """'2. berlaku 2 November 2020 s.d. 29 Desember 2022 · UU 11/2020 · bersyarat'."""
    parts = [f"{number}. {version['validity']}", version["published_in"]]
    if version["status"] in STATUS_BADGES:
        parts.append(STATUS_BADGES[version["status"]])
    return " · ".join(parts)


def history_html(found: dict | None, today: date | None = None) -> str:
    """An article's history: each wording as a stretch of a bar from its first day to today,
    coloured by its status, then the timeline as code states it."""
    if found is None:
        return notice("Pasal ini tidak ada dalam sumber PasalKini.")
    parts = [f"<h3>{esc(found['label'])}</h3>", history_bar(found["versions"], today)]
    if found["timeline"]:
        parts.append(timeline_html(found["timeline"]))
    return '<div class="pk-article">' + "".join(parts) + "</div>"


def history_bar(versions: list[dict], today: date | None = None) -> str:
    """One stretch per version, in proportion to how long it applied, numbered as in the list
    below. A deleted article's stretch is hatched."""
    if not versions:
        return ""
    first = date.fromisoformat(versions[0]["valid_from"])
    last = today or date.today()
    span = max((last - first).days, 1)
    stretches = []
    for number, version in enumerate(versions, start=1):
        begin = date.fromisoformat(version["valid_from"])
        end = date.fromisoformat(version["valid_to"]) if version["valid_to"] else last
        left = 100 * (begin - first).days / span
        width = max(100 * (end - begin).days / span, 0.6)
        label = f"{number}. {version['validity']}, {version['published_in']}"
        shown = str(number) if width >= 4 else ""
        stretches.append(
            f'<span class="pk-stretch pk-{esc(version["status"])}" title="{esc(label)}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%">{shown}</span>'
        )
    return (
        f'<div class="pk-bar" role="img" aria-label="Masa berlaku tiap versi">'
        f"{''.join(stretches)}</div>"
        f'<div class="pk-axis"><span>{esc(format_date(first))}</span>'
        f"<span>{esc(format_date(last))}</span></div>"
        '<div class="pk-legend"><span class="pk-key pk-in_force"></span>berlaku '
        '<span class="pk-key pk-conditional"></span>berlaku bersyarat '
        '<span class="pk-key pk-repealed"></span>dihapus</div>'
    )


def versions_html(found: dict | None) -> str:
    """Every version of the article in full, oldest first."""
    if found is None:
        return ""
    parts = ["<h4>Semua versi</h4>"]
    for number, version in enumerate(found["versions"], start=1):
        parts.append(
            f'<section class="pk-version"><h5>{esc(version_label(number, version))}</h5>'
            f'<div class="pk-meta">{source_code(version["source_id"])}</div>'
        )
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
        parts.append("</section>")
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
        parts.append(f"<h4>{esc(article['label'])}{badge(article['status'])}</h4>")
        parts.append(
            f'<div class="pk-meta">{esc(article["validity"])}; bunyi dari '
            f'<code class="pk-id">{esc(article["source_id"])}</code></div>'
        )
        parts.append(legal(article["text"]))
    return '<div class="pk-article">' + "".join(parts) + "</div>"


def calculation_html(result: dict, wage: int | None) -> str:
    """A calculator result: the total first, then one row per component with its formula and
    legal basis, then what else the reader should know."""
    if result["unsupported"]:
        return notice(result["unsupported"])
    titles = {source["source_id"]: source["title"] for source in result["sources"]}
    rows = "".join(
        f"<tr><td>{esc(line['component'])}</td><td>{esc(line['formula'])}</td>"
        f'<td class="pk-amount">{esc(rupiah(line["amount"]))}</td>'
        f"<td>{esc('; '.join(titles.get(b, b).split(' (')[0] for b in line['basis']))}</td></tr>"
        for line in result["lines"]
    )
    least = "paling sedikit " if result["minimum"] else ""
    parts = []
    if result["total"] is not None:
        total = f"{least}{rupiah(result['total'])}"
        parts.append(
            '<div class="pk-asof"><span class="pk-asof-lead">Jumlah yang dapat dihitung</span>'
            f'<span class="pk-date">{esc(total)}</span></div>'
        )
    elif result["total_months_of_wage"]:
        months = f"{result['total_months_of_wage']:g}".replace(".", ",")
        parts.append(
            '<div class="pk-asof"><span class="pk-asof-lead">Jumlah, dalam bulan upah</span>'
            f'<span class="pk-date">{esc(least + months)} bulan upah</span></div>'
        )
    regime = instrument_label(result["regime"])
    parts.append(
        f'<p class="pk-calc-basis">Menurut {esc(regime)}, dengan masa kerja '
        f"{esc(result['service'])} dan upah sebulan {esc(rupiah(wage))}.</p>"
    )
    if result["reason"]:
        parts.append(f'<div class="pk-meta">Alasan PHK: {esc(result["reason"])}</div>')
    if rows:
        parts.append(
            '<table class="pk-table"><thead><tr><th>Komponen</th><th>Rumus</th>'
            '<th class="pk-amount">Jumlah</th>'
            f"<th>Dasar hukum</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    if result["other_reasons_same_article"]:
        parts.append("<h4>Alasan lain dalam pasal yang sama</h4>")
        parts.append(items(result["other_reasons_same_article"]))
    if result["notes"]:
        parts.append("<h4>Catatan</h4>" + items(result["notes"]))
    parts.append(
        '<footer class="pk-small"><p>Dihitung oleh program dari aturan yang berlaku pada '
        f"{esc(day_text(result['as_of']))}, bukan oleh AI. Periksa juga perjanjian kerja, "
        "peraturan perusahaan dan perjanjian kerja bersama Anda.</p></footer>"
    )
    return '<div class="pk-answer">' + "".join(parts) + "</div>"

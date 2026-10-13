"""The four screens (Gradio), mounted at /ui by the API.

Tanya           a question and an optional date → the checked answer and its sources; a cited
                article opens in full, as it stood on that date
Riwayat Pasal   one article's timeline and versions, and the word-level changes between any two
Konsolidasi     a law as it stood on a date
Kalkulator      severance and PKWT compensation, by rule

Every screen calls pasalkini.service.Service in-process; nothing here reads data or talks to the
model itself. What is shown is built in pasalkini.ui.render.

Nothing is sent outside the machine: Gradio's usage analytics are off and the theme uses the
system's fonts instead of fonts fetched from Google.
"""

from datetime import date

import gradio as gr
from fastapi import FastAPI

from pasalkini.service import Service
from pasalkini.temporal.query import format_date
from pasalkini.tools.pesangon import CalculatorError
from pasalkini.ui.render import (
    answer_html,
    calculation_html,
    diff_html,
    history_html,
    law_html,
    notice,
    provision_html,
    version_label,
)

PATH = "/ui"
HEADER = """<header class="pk-head">
<h1>PasalKini</h1>
<p>Hukum ketenagakerjaan Indonesia, menurut bunyi yang berlaku pada tanggal yang Anda tanyakan.</p>
</header>"""
BANNER = """<div class="pk-banner">
<p><strong>Informasi hukum, bukan nasihat hukum.</strong> Jawaban disusun oleh AI yang berjalan di
komputer ini, dari teks peraturan resmi, dan dapat keliru: selalu periksa kutipan sumbernya.</p>
<details><summary>Selengkapnya</summary>
<p>PasalKini menjawab menurut bunyi peraturan yang berlaku pada tanggal yang Anda tanyakan, bukan
menurut bunyi yang paling mirip dengan pertanyaan. Untuk perselisihan atau tenggat waktu, hubungi
Dinas Ketenagakerjaan, serikat pekerja, atau Lembaga Bantuan Hukum (LBH).</p>
<p>Pertanyaan dicatat di komputer ini tanpa data pribadi selama 30 hari, lalu dihapus. Jangan
menuliskan nama lengkap, NIK atau nomor telepon.</p>
</details>
</div>"""
EXAMPLES = [
    ["Kalau saya bekerja 5 hari dalam seminggu, berapa hari istirahat mingguan?", "2019-06-01"],
    ["Berapa jam maksimal lembur dalam sehari?", "2019-06-01"],
    ["Berapa jam maksimal lembur dalam sehari?", "2021-06-01"],
    ["Apakah Pasal 64 UU 13/2003 masih berlaku?", None],
    [
        "Saya di-PHK bulan Maret 2024 karena perusahaan efisiensi untuk mencegah kerugian, "
        "setelah 6 tahun bekerja dengan upah Rp5.000.000. Berapa pesangon saya?",
        None,
    ],
]

# Colours carry meaning: ink and paper; one blue for what can be acted on; green, amber and
# brick only for an article's status (in force, conditional, deleted). Fonts are the system's:
# nothing is fetched from the internet. Quoted law is set in a serif, so that the text of a
# regulation never looks like a sentence written by the model.
INK, INK_DARK = "#1E2A3A", "#E3E7ED"
MUTED, MUTED_DARK = "#5A6472", "#9BA4B1"
PAPER, PAPER_DARK = "#FFFFFF", "#1A2029"
PAGE, PAGE_DARK = "#F2F3F1", "#12161D"
LINE, LINE_DARK = "#D8DBD5", "#2D3542"
BLUE, BLUE_DARK = "#2B4C8C", "#93ACDD"
THEME = gr.themes.Base(
    font=["Segoe UI", "system-ui", "Roboto", "sans-serif"],
    font_mono=["Consolas", "ui-monospace", "monospace"],
).set(
    body_background_fill=PAGE,
    body_background_fill_dark=PAGE_DARK,
    body_text_color=INK,
    body_text_color_dark=INK_DARK,
    body_text_color_subdued=MUTED,
    body_text_color_subdued_dark=MUTED_DARK,
    background_fill_primary=PAPER,
    background_fill_primary_dark=PAPER_DARK,
    background_fill_secondary=PAGE,
    background_fill_secondary_dark=PAGE_DARK,
    block_background_fill=PAPER,
    block_background_fill_dark=PAPER_DARK,
    block_border_color=LINE,
    block_border_color_dark=LINE_DARK,
    border_color_primary=LINE,
    border_color_primary_dark=LINE_DARK,
    block_shadow="none",
    block_shadow_dark="none",
    block_radius="4px",
    input_radius="3px",
    button_large_radius="3px",
    button_medium_radius="3px",
    button_small_radius="3px",
    input_background_fill=PAPER,
    input_background_fill_dark=PAGE_DARK,
    input_border_color=LINE,
    input_border_color_dark=LINE_DARK,
    input_border_color_focus=BLUE,
    input_border_color_focus_dark=BLUE_DARK,
    color_accent=BLUE,
    color_accent_soft="#E5EBF5",
    color_accent_soft_dark="#243250",
    border_color_accent=BLUE,
    border_color_accent_dark=BLUE_DARK,
    link_text_color=BLUE,
    link_text_color_dark=BLUE_DARK,
    button_primary_background_fill=BLUE,
    button_primary_background_fill_dark=BLUE_DARK,
    button_primary_background_fill_hover="#213C70",
    button_primary_background_fill_hover_dark="#B0C3E8",
    button_primary_border_color=BLUE,
    button_primary_border_color_dark=BLUE_DARK,
    button_primary_text_color="#FFFFFF",
    button_primary_text_color_dark="#0F1726",
    button_secondary_background_fill=PAPER,
    button_secondary_background_fill_dark=PAPER_DARK,
    button_secondary_border_color=LINE,
    button_secondary_border_color_dark=LINE_DARK,
    checkbox_label_background_fill_selected="#E5EBF5",
    checkbox_label_background_fill_selected_dark="#243250",
    checkbox_background_color_selected=BLUE,
    checkbox_background_color_selected_dark=BLUE_DARK,
)
CSS = """
:root { --pk-blue: #2B4C8C; --pk-green: #2F6B3F; --pk-amber: #8A6100; --pk-brick: #8E2B2B;
  --pk-serif: Cambria, Georgia, "Times New Roman", serif; }
.dark { --color-accent: #93ACDD; --pk-blue: #93ACDD;
  --pk-green: #84C295; --pk-amber: #DDB45A; --pk-brick: #DE8E8E; }
.gradio-container { max-width: 880px !important; margin: 0 auto !important; }

.pk-head { padding: 18px 0 4px; }
.pk-head h1 { font-size: 1.9em; font-weight: 700; letter-spacing: -0.01em; margin: 0; }
.pk-head p { margin: 2px 0 0; color: var(--body-text-color-subdued); }
.pk-banner { border-left: 3px solid var(--pk-amber); padding: 2px 0 2px 14px;
  font-size: 0.92em; line-height: 1.5; }
.pk-banner p { margin: 4px 0; }
.pk-banner summary { cursor: pointer; color: var(--link-text-color); width: fit-content; }
.pk-banner summary:focus-visible { outline: 2px solid var(--pk-blue); outline-offset: 2px; }

.pk-when { align-items: flex-end !important; }
.pk-ask { flex-grow: 0 !important; min-height: 44px; margin-bottom: 1px; }
.pk-hint { font-size: 0.86em; color: var(--body-text-color-subdued); margin: -4px 0 0; }
.pk-status { color: var(--body-text-color-subdued); min-height: 1.4em; }
.pk-examples { gap: 0 !important; }
.pk-examples-title { font-size: 0.92em; color: var(--body-text-color-subdued); margin: 6px 0 2px; }
.pk-example { justify-content: flex-start !important; text-align: left !important;
  border: none !important; background: none !important; box-shadow: none !important;
  color: var(--link-text-color) !important; font-weight: 400 !important;
  padding: 3px 10px !important; min-height: 0 !important; white-space: normal !important;
  font-size: 0.95em !important; }
.pk-example:hover { text-decoration: underline; }

.pk-answer, .pk-article { line-height: 1.6; }
.pk-asof { margin: 4px 0 10px; }
.pk-asof-lead { display: block; font-size: 0.9em; color: var(--body-text-color-subdued); }
.pk-date { font-size: 1.45em; font-weight: 700; letter-spacing: -0.01em; }
.pk-asof-source { font-size: 0.86em; color: var(--body-text-color-subdued); }
.pk-said { font-size: 1.1em; margin: 6px 0 18px; white-space: pre-wrap; max-width: 68ch; }
.pk-answer h4, .pk-article h4 { font-size: 0.98em; font-weight: 600; margin: 18px 0 6px; }
.pk-legal { white-space: pre-wrap; font-family: var(--pk-serif); font-size: 1.04em;
  font-weight: 400;
  border-left: 2px solid var(--border-color-primary); padding: 2px 0 2px 14px;
  margin: 6px 0 12px; max-width: 72ch; }
.pk-record { white-space: pre-wrap; font-size: 0.93em; padding: 2px 0 2px 14px;
  border-left: 2px solid var(--border-color-primary); margin: 6px 0 12px; }
.pk-passages { list-style: none; padding: 0; margin: 0; }
.pk-passages li { margin: 0 0 12px; }
.pk-passages blockquote { margin: 4px 0 0; padding: 2px 0 2px 14px; white-space: pre-wrap;
  font-family: var(--pk-serif); font-size: 1.04em; max-width: 72ch;
  font-weight: 400; font-style: normal; border-left: 3px solid var(--pk-blue); }
.pk-earlier blockquote { border-left: 3px dotted var(--body-text-color-subdued);
  color: var(--body-text-color-subdued); }
.pk-later blockquote { border-left: 3px dashed var(--pk-blue); }
.pk-nearest blockquote { border-left-color: var(--border-color-primary); }
.pk-source { font-weight: 600; }
.pk-id { font-size: 0.8em; color: var(--body-text-color-subdued); background: none;
  padding: 0; margin-left: 4px; }
.pk-meta { font-size: 0.85em; color: var(--body-text-color-subdued); margin: 4px 0; }
.pk-referral { font-weight: 600; }
.pk-notice { border-left: 3px solid var(--pk-amber); padding: 6px 0 6px 14px; }
.pk-badge { font-size: 0.72em; font-weight: 600; padding: 1px 8px; border-radius: 10px;
  border: 1px solid var(--pk-amber); color: var(--pk-amber); vertical-align: middle; }
.pk-diff del { background: rgba(142, 43, 43, 0.16); text-decoration: line-through; }
.pk-diff ins { background: rgba(47, 107, 63, 0.18); text-decoration: underline; }
.pk-table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; }
.pk-table th, .pk-table td { border-bottom: 1px solid var(--border-color-primary);
  padding: 6px 10px; text-align: left; vertical-align: top; }
.pk-amount { text-align: right !important; white-space: nowrap; }
.pk-foot { font-size: 0.85em; color: var(--body-text-color-subdued); margin: 24px 0 8px; }
@media (max-width: 640px) { .pk-date { font-size: 1.25em; } .pk-head h1 { font-size: 1.6em; } }
"""


def day_of(value: object) -> date | None:
    """The date picker's value: 'YYYY-MM-DD', with or without a time after it, or nothing."""
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]) if text else None
    except ValueError:
        return None


def chips(payload: dict) -> list[tuple[str, str]]:
    """One choice per cited article: its name, and what to open (article and date). A wording
    that had ended by the question's date, or began after it, is opened as it stood when it
    began."""
    found: dict[str, str] = {}
    groups = [
        (payload["citations"] + payload["nearest"], None),
        (payload["earlier"], "valid_from"),
        (payload["later"], "valid_from"),
    ]
    for passages, own_date in groups:
        for passage in passages:
            day = passage.get(own_date) if own_date else payload["as_of"]
            name = passage["title"].split(" (")[0]
            found.setdefault(f"{passage['provision_id']}@{day}", name)
    return [(name, value) for value, name in found.items()]


def build(service: Service) -> gr.Blocks:
    laws = service.instruments()
    law_choices = [(f"{law['name']} ({law['articles']} pasal)", law["id"]) for law in laws]
    first_law = laws[0]["id"] if laws else None

    def article_choices(instrument_id: str | None) -> list[tuple[str, str]]:
        if not instrument_id:
            return []
        return [(a["label"], a["provision_id"]) for a in service.articles(instrument_id)]

    # --- Tanya ---

    def ask(question: str, day: object):
        closed = gr.update(choices=[], value=None, visible=False)
        yield "Memulai…", "", closed, ""
        for kind, data in service.ask_events(question or "", day_of(day)):
            if kind == "stage":
                yield f"{data['label']}…", gr.skip(), gr.skip(), gr.skip()
            elif kind == "answer":
                found = chips(data)
                opened = gr.update(choices=found, value=None, visible=bool(found))
                yield "", answer_html(data), opened, ""
            else:
                yield "", notice(data["detail"]), closed, ""

    def open_article(choice: str | None) -> str:
        if not choice:
            return ""
        provision_id, _, day = choice.rpartition("@")
        return provision_html(service.provision(provision_id, date.fromisoformat(day)))

    # --- Riwayat Pasal ---

    def show_history(provision_id: str | None):
        found = service.history(provision_id) if provision_id else None
        if found is None:
            empty = gr.update(choices=[], value=None)
            return ("" if not provision_id else history_html(None)), empty, empty, ""
        versions = found["versions"]
        choices = [(version_label(n, v), n - 1) for n, v in enumerate(versions, start=1)]
        # Compare the latest wording with the one before it that reads differently. A deletion
        # in between has no wording to compare with.
        last = len(versions) - 1
        earlier = [
            n
            for n in range(last)
            if versions[n]["text"] != versions[last]["text"] and versions[n]["status"] != "repealed"
        ]
        before = earlier[-1] if earlier else 0
        return (
            history_html(found),
            gr.update(choices=choices, value=before),
            gr.update(choices=choices, value=last),
            compare(provision_id, before, last),
        )

    def compare(provision_id: str | None, old: int | None, new: int | None) -> str:
        found = service.history(provision_id) if provision_id else None
        if found is None or old is None or new is None:
            return ""
        versions = found["versions"]
        if old == new or versions[old]["text"] == versions[new]["text"]:
            return notice("Kedua versi berbunyi sama.")
        return diff_html(versions[old]["text"], versions[new]["text"])

    # --- Konsolidasi ---

    def show_law(instrument_id: str | None, day: object, only: str) -> str:
        if not instrument_id:
            return notice("Pilih peraturan lebih dulu.")
        numbers = [n for n in (only or "").replace(";", ",").split(",") if n.strip()]
        return law_html(service.law(instrument_id, day_of(day) or service.today(), numbers))

    # --- Kalkulator ---

    def reason_choices(day: object):
        reasons = service.reasons(day_of(day) or service.today())
        return gr.update(choices=[(text, code) for code, text in reasons.items()], value=None)

    def severance(end, start, wage, reason, leave, days, micro) -> str:
        end_day = day_of(end)
        if end_day is None:
            return notice("Isi tanggal PHK.")
        if not reason and service.reasons(end_day):
            return notice("Pilih alasan PHK: besaran pesangon bergantung padanya.")
        wage = int(wage) if wage else None
        try:
            result = service.severance(
                day_of(start),
                end_day,
                wage,
                reason or "",
                leave_days=int(leave or 0),
                days_per_week=int(days),
                micro_or_small=bool(micro),
            )
        except CalculatorError as error:
            return notice(f"Tidak dapat dihitung: {error}.")
        return calculation_html(result, wage)

    def compensation(start, end, wage, micro) -> str:
        start_day, end_day = day_of(start), day_of(end)
        if start_day is None or end_day is None:
            return notice("Isi tanggal mulai dan tanggal berakhirnya kontrak.")
        wage = int(wage) if wage else None
        try:
            result = service.pkwt_compensation(start_day, end_day, wage, micro_or_small=bool(micro))
        except CalculatorError as error:
            return notice(f"Tidak dapat dihitung: {error}.")
        return calculation_html(result, wage)

    today = service.today().isoformat()
    with gr.Blocks(title="PasalKini", analytics_enabled=False) as blocks:
        gr.HTML(HEADER)
        gr.HTML(BANNER)

        with gr.Tab("Tanya"):
            question = gr.Textbox(
                label="Pertanyaan",
                placeholder="Misalnya: Berapa jam maksimal lembur dalam sehari?",
                lines=3,
            )
            # The date is what the answer depends on, so it reads as the rest of the question.
            with gr.Row(elem_classes="pk-when"):
                asked_day = gr.DateTime(
                    label="Menurut hukum yang berlaku pada",
                    include_time=False,
                    type="string",
                    scale=3,
                )
                ask_button = gr.Button(
                    "Tanya", variant="primary", scale=1, min_width=120, elem_classes="pk-ask"
                )
            gr.HTML(
                '<p class="pk-hint">Kosongkan tanggal untuk hari ini. Tanggal yang ditulis di '
                "dalam pertanyaan (misalnya “Maret 2019”) didahulukan.</p>"
            )
            with gr.Column(elem_classes="pk-examples"):
                gr.HTML('<p class="pk-examples-title">Coba salah satu pertanyaan ini:</p>')
                for text, day in EXAMPLES:
                    shown = f"{text} ({format_date(date.fromisoformat(day))})" if day else text
                    example = gr.Button(shown, size="sm", elem_classes="pk-example")
                    example.click(lambda t=text, d=day: (t, d), None, [question, asked_day])
            status = gr.Markdown(elem_classes="pk-status")
            answer = gr.HTML()
            cited = gr.Radio(
                label="Buka pasal yang dikutip, menurut bunyinya pada tanggal itu",
                choices=[],
                visible=False,
            )
            article = gr.HTML()
            outputs = [status, answer, cited, article]
            ask_button.click(ask, [question, asked_day], outputs)
            question.submit(ask, [question, asked_day], outputs)
            cited.change(open_article, cited, article)

        with gr.Tab("Riwayat Pasal"):
            with gr.Row():
                history_law = gr.Dropdown(law_choices, value=first_law, label="Peraturan")
                history_article = gr.Dropdown(
                    article_choices(first_law), value=None, label="Pasal", filterable=True
                )
            timeline = gr.HTML()
            gr.Markdown("### Bandingkan dua versi")
            with gr.Row():
                old_version = gr.Dropdown([], label="Versi lama", type="value")
                new_version = gr.Dropdown([], label="Versi baru", type="value")
            changes = gr.HTML()
            history_law.change(
                lambda law: gr.update(choices=article_choices(law), value=None),
                history_law,
                history_article,
            )
            history_article.change(
                show_history, history_article, [timeline, old_version, new_version, changes]
            )
            versions_picked = [history_article, old_version, new_version]
            old_version.input(compare, versions_picked, changes)
            new_version.input(compare, versions_picked, changes)

        with gr.Tab("Konsolidasi"):
            with gr.Row():
                law = gr.Dropdown(law_choices, value=first_law, label="Peraturan", scale=2)
                law_day = gr.DateTime(
                    value=today, label="Tanggal", include_time=False, type="string", scale=1
                )
                only = gr.Textbox(
                    label="Hanya pasal (opsional)", placeholder="Misalnya: 59, 61A", scale=1
                )
            law_button = gr.Button("Tampilkan", variant="primary")
            law_text = gr.HTML()
            law_button.click(show_law, [law, law_day, only], law_text)

        with gr.Tab("Kalkulator Pesangon"):
            gr.Markdown(
                "Dihitung oleh program dari aturan yang berlaku pada tanggal PHK, bukan oleh AI. "
                "Kosongkan upah atau tanggal mulai bekerja jika tidak diketahui: hasilnya lalu "
                "berupa pengali atau bulan upah."
            )
            with gr.Tab("Pesangon saat PHK"):
                with gr.Row():
                    end = gr.DateTime(
                        value=today, label="Tanggal PHK", include_time=False, type="string"
                    )
                    start = gr.DateTime(
                        label="Tanggal mulai bekerja", include_time=False, type="string"
                    )
                    wage = gr.Number(
                        label="Upah sebulan (Rp)",
                        info="Upah pokok dan tunjangan tetap.",
                        precision=0,
                        minimum=0,
                    )
                initial = service.reasons(service.today())
                reason = gr.Dropdown(
                    [(text, code) for code, text in initial.items()],
                    value=None,
                    label="Alasan PHK",
                    info="Pilihan mengikuti aturan yang berlaku pada tanggal PHK.",
                )
                with gr.Row():
                    leave = gr.Number(
                        value=0, label="Sisa cuti tahunan (hari)", precision=0, minimum=0
                    )
                    days = gr.Radio([5, 6], value=5, label="Hari kerja per minggu")
                    micro = gr.Checkbox(label="Usaha mikro atau usaha kecil")
                severance_button = gr.Button("Hitung", variant="primary")
                severance_result = gr.HTML()
                end.change(reason_choices, end, reason)
                severance_button.click(
                    severance, [end, start, wage, reason, leave, days, micro], severance_result
                )
            with gr.Tab("Kompensasi saat PKWT berakhir"):
                with gr.Row():
                    contract_start = gr.DateTime(
                        label="Tanggal mulai kontrak", include_time=False, type="string"
                    )
                    contract_end = gr.DateTime(
                        value=today,
                        label="Tanggal kontrak berakhir",
                        include_time=False,
                        type="string",
                    )
                    contract_wage = gr.Number(label="Upah sebulan (Rp)", precision=0, minimum=0)
                    contract_micro = gr.Checkbox(label="Usaha mikro atau usaha kecil")
                compensation_button = gr.Button("Hitung", variant="primary")
                compensation_result = gr.HTML()
                compensation_button.click(
                    compensation,
                    [contract_start, contract_end, contract_wage, contract_micro],
                    compensation_result,
                )

        documents = sum(i.status == "active" for i in service.manifest.instruments)
        gr.Markdown(
            elem_classes="pk-foot",
            value=f"Sumber: {documents} peraturan dan putusan Mahkamah Konstitusi dari situs resmi "
            f"pemerintah; perubahan terakhir yang tercatat berlaku sejak "
            f"{format_date(service.law_as_of(service.today()) or service.today())}. "
            "Teks berasal dari PDF resmi dan dapat memuat salah baca (OCR): untuk keperluan "
            "resmi, pakai naskah resminya. API: [/docs](/docs).",
        )
    return blocks


def mount(app: FastAPI, service: Service) -> FastAPI:
    return gr.mount_gradio_app(
        app, build(service), path=PATH, theme=THEME, css=CSS, footer_links=["settings"]
    )

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
BANNER = """<div class="pk-banner">
<strong>Informasi hukum, bukan nasihat hukum.</strong> PasalKini menjawab dengan bantuan AI
(model bahasa yang berjalan di komputer ini) dari teks peraturan resmi, menurut bunyi yang
berlaku pada tanggal yang Anda tanyakan. Jawabannya dapat keliru: selalu periksa kutipan
sumbernya. Untuk perselisihan atau tenggat waktu, hubungi Dinas Ketenagakerjaan, serikat
pekerja, atau Lembaga Bantuan Hukum (LBH).<br>
<strong>Jangan menuliskan data pribadi</strong> (nama lengkap, NIK, nomor telepon). Pertanyaan
dicatat tanpa data pribadi di komputer ini selama 30 hari, lalu dihapus.
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
THEME = gr.themes.Default(
    font=["system-ui", "Segoe UI", "Roboto", "sans-serif"],
    font_mono=["ui-monospace", "Consolas", "monospace"],
)
CSS = """
.pk-banner { border: 1px solid var(--border-color-primary); border-left: 4px solid #d97706;
  border-radius: 6px; padding: 10px 14px; font-size: 0.92em; line-height: 1.5;
  background: var(--background-fill-secondary); }
.pk-answer, .pk-article { line-height: 1.55; }
.pk-asof { color: var(--body-text-color-subdued); margin-bottom: 6px; }
.pk-said { font-size: 1.08em; font-weight: 600; margin: 6px 0 12px; white-space: pre-wrap; }
.pk-legal { white-space: pre-wrap; border-left: 3px solid var(--border-color-primary);
  padding: 4px 0 4px 12px; margin: 6px 0 12px; }
.pk-passages { padding-left: 18px; }
.pk-passages blockquote { margin: 4px 0 10px; padding: 2px 0 2px 12px; white-space: pre-wrap;
  border-left: 3px solid var(--color-accent); }
.pk-source { font-weight: 600; }
.pk-id { font-size: 0.82em; color: var(--body-text-color-subdued); }
.pk-meta { font-size: 0.86em; color: var(--body-text-color-subdued); margin: 4px 0; }
.pk-referral { font-weight: 600; }
.pk-notice { border: 1px solid var(--border-color-primary); border-radius: 6px;
  padding: 10px 14px; background: var(--background-fill-secondary); }
.pk-badge { font-size: 0.72em; font-weight: 600; padding: 1px 8px; border-radius: 10px;
  border: 1px solid #d97706; color: #d97706; vertical-align: middle; }
.pk-diff del { background: rgba(220, 38, 38, 0.22); text-decoration: line-through; }
.pk-diff ins { background: rgba(22, 163, 74, 0.25); text-decoration: underline; }
.pk-table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; }
.pk-table th, .pk-table td { border: 1px solid var(--border-color-primary); padding: 6px 10px;
  text-align: left; vertical-align: top; }
.pk-amount { text-align: right !important; white-space: nowrap; }
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
    """One choice per cited article: its name, and what to open (article and date). Law that
    began after the question's date is opened as it stood when it began."""
    found: dict[str, str] = {}
    groups = [
        (payload["citations"] + payload["nearest"], None),
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
        gr.Markdown("# PasalKini\nHukum ketenagakerjaan Indonesia, menurut tanggal.")
        gr.HTML(BANNER)

        with gr.Tab("Tanya"):
            with gr.Row():
                question = gr.Textbox(
                    label="Pertanyaan",
                    placeholder="Misalnya: Berapa jam maksimal lembur dalam sehari?",
                    lines=3,
                    scale=4,
                )
                asked_day = gr.DateTime(
                    label="Tanggal (opsional)",
                    info="Kosong: hari ini. Tanggal di dalam pertanyaan didahulukan.",
                    include_time=False,
                    type="string",
                    scale=1,
                )
            ask_button = gr.Button("Tanya", variant="primary")
            status = gr.Markdown()
            answer = gr.HTML()
            cited = gr.Radio(
                label="Buka pasal yang dikutip, menurut bunyinya pada tanggal itu",
                choices=[],
                visible=False,
            )
            article = gr.HTML()
            gr.Examples(EXAMPLES, [question, asked_day], label="Contoh pertanyaan")
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
            f"Sumber: {documents} peraturan dan putusan Mahkamah Konstitusi dari situs resmi "
            f"pemerintah; perubahan terakhir yang tercatat berlaku sejak "
            f"{format_date(service.law_as_of(service.today()) or service.today())}. "
            "Teks berasal dari PDF resmi dan dapat memuat salah baca (OCR): untuk keperluan "
            "resmi, pakai naskah resminya. API: [/docs](/docs)."
        )
    return blocks


def mount(app: FastAPI, service: Service) -> FastAPI:
    return gr.mount_gradio_app(
        app, build(service), path=PATH, theme=THEME, css=CSS, footer_links=["settings"]
    )

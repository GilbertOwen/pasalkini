"""The HTTP API. Every endpoint is a thin wrapper over pasalkini.service.Service.

POST /ask                          a question, answered as a stream of server-sent events:
                                   'stage' as each stage starts, then 'answer' (or 'error')
POST /ask/json                     the same, as one JSON response
GET  /provisions/{id}?as_of=       an article, or a ruling point, as it stood on a date
GET  /provisions/{id}/history      every version of an article, with word-level changes
GET  /laws                         the laws and regulations that can be browsed
GET  /laws/{id}?as_of=&pasal=      one of them as it stood on a date
GET  /calc/pesangon/reasons?date=  dismissal reasons under the rules of a date
POST /calc/pesangon                severance, computed by rule
POST /calc/kompensasi-pkwt         compensation at the end of a fixed-term contract
GET  /health                       corpus, model server, cache

The answer is not streamed word by word: nothing the model writes is shown before code has
checked it, so the stream carries the stages and then the whole checked answer.

The UI is mounted at /ui (pasalkini.ui.app) and / redirects there; /docs is the OpenAPI page.
"""

from collections.abc import Iterable
from datetime import date as Date
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from pasalkini import __version__
from pasalkini.answer.followup import Turn
from pasalkini.privacy.redact import redact
from pasalkini.service import AS_OF_SOURCES, MAX_QUESTION_CHARS, ModelUnavailable, Service
from pasalkini.tools.pesangon import CalculatorError

DESCRIPTION = (
    "Informasi hukum ketenagakerjaan Indonesia menurut tanggal. **Informasi hukum, bukan "
    "nasihat hukum**: jawaban disusun dengan bantuan AI dari teks peraturan resmi dan dapat "
    "keliru."
)
AsOf = Annotated[
    Date | None,
    Query(description="Tanggal yang menentukan hukum yang berlaku (YYYY-MM-DD). Kosong: hari ini."),
]


class TurnIn(BaseModel):
    """An earlier question of the conversation and its answer, as /ask returned them."""

    question: str = Field(max_length=MAX_QUESTION_CHARS)
    answer: str = Field(max_length=20_000)
    as_of: Date
    as_of_source: Literal["question", "date_picker", "today"] = "question"


class AskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_CHARS,
        examples=["Berapa jam maksimal lembur dalam sehari?"],
    )
    date: Date | None = Field(
        default=None,
        description=(
            "Tanggal dari pemilih tanggal. Tanggal yang disebut di dalam pertanyaan didahulukan; "
            "tanpa keduanya dipakai hari ini."
        ),
        examples=["2019-06-01"],
    )
    history: list[TurnIn] = Field(
        default=[],
        max_length=20,
        description="Pertanyaan dan jawaban sebelumnya, terlama dulu: pertanyaan lanjutan "
        "('kalau tahun 2022?') ditulis ulang menjadi pertanyaan lengkap.",
    )


class SeveranceRequest(BaseModel):
    tanggal_phk: Date
    alasan: str = Field(description="Kode alasan PHK dari GET /calc/pesangon/reasons.")
    tanggal_mulai: Date | None = Field(default=None, description="Kosong: masa kerja tidak ada.")
    upah_bulanan: int | None = Field(
        default=None, gt=0, description="Upah pokok dan tunjangan tetap sebulan, dalam rupiah."
    )
    sisa_cuti_hari: int = Field(default=0, ge=0, le=366)
    hari_kerja_per_minggu: Literal[5, 6] = 5
    usaha_mikro_kecil: bool = False


class CompensationRequest(BaseModel):
    tanggal_mulai: Date
    tanggal_berakhir: Date
    upah_bulanan: int | None = Field(default=None, gt=0)
    usaha_mikro_kecil: bool = False


def turns(body: AskRequest) -> list[Turn]:
    sources = {code: name for name, code in AS_OF_SOURCES.items()}
    return [
        Turn(redact(t.question).text, t.answer, t.as_of, sources[t.as_of_source])
        for t in body.history
    ]


def create_app(service: Service | None = None, ui: bool = True) -> FastAPI:
    """`service`: loaded from disk when not given. `ui`: mount the Gradio screens at /ui."""
    service = service or Service.load()
    app = FastAPI(title="PasalKini", version=__version__, description=DESCRIPTION)

    @app.exception_handler(ModelUnavailable)
    def model_unavailable(request: Request, error: ModelUnavailable) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=503, headers={"Retry-After": "30"})

    @app.exception_handler(CalculatorError)
    def cannot_calculate(request: Request, error: CalculatorError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.get("/health", tags=["app"])
    def health() -> dict:
        return service.health()

    @app.post("/ask", response_class=EventSourceResponse, tags=["tanya"])
    def ask(body: AskRequest) -> Iterable[ServerSentEvent]:
        """A question, answered as a stream: `stage` events while the pipeline works, then one
        `answer` event with the whole checked answer, or one `error` event."""
        for kind, data in service.ask_events(body.question, body.date, turns(body)):
            yield ServerSentEvent(event=kind, data=data)

    @app.post("/ask/json", tags=["tanya"])
    def ask_json(body: AskRequest) -> dict:
        """The same question, answered in one response."""
        try:
            return service.ask(body.question, body.date, history=turns(body))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    # The history route comes first: a provision ID has slashes in it, so the plain route's
    # path parameter would swallow '/history'.
    @app.get("/provisions/{provision_id:path}/history", tags=["riwayat pasal"])
    def provision_history(provision_id: str) -> dict:
        """Every version of one article, oldest first, each with the word-level changes from
        the one before it."""
        found = service.history(provision_id)
        if found is None:
            raise HTTPException(404, f"{provision_id} tidak ada dalam sumber PasalKini.")
        return found

    @app.get("/provisions/{provision_id:path}", tags=["riwayat pasal"])
    def provision(provision_id: str, as_of: AsOf = None) -> dict:
        """One article (`uu-13-2003/pasal-59`) or ruling point as it stood on the date."""
        found = service.provision(provision_id, as_of or service.today())
        if found is None:
            raise HTTPException(404, f"{provision_id} tidak ada dalam sumber PasalKini.")
        if not found["exists_on_date"]:
            raise HTTPException(404, found["message"])
        return found

    @app.get("/laws", tags=["konsolidasi"])
    def laws() -> list[dict]:
        return service.instruments()

    @app.get("/laws/{instrument_id}", tags=["konsolidasi"])
    def law(
        instrument_id: str,
        as_of: AsOf = None,
        pasal: Annotated[
            list[str] | None, Query(description="Hanya pasal ini, misalnya 59 atau 61A.")
        ] = None,
    ) -> dict:
        """A law or regulation as it stood on the date: each article in the wording that
        applied, with deleted articles left out."""
        found = service.law(instrument_id, as_of or service.today(), pasal)
        if found is None:
            raise HTTPException(404, f"{instrument_id} tidak ada dalam sumber PasalKini.")
        return found

    @app.get("/calc/pesangon/reasons", tags=["kalkulator"])
    def reasons(
        date: Annotated[Date | None, Query(description="Tanggal PHK. Kosong: hari ini.")] = None,
    ) -> dict[str, str]:
        """Dismissal reasons under the rules in force on the date: code and description."""
        return service.reasons(date or service.today())

    @app.post("/calc/pesangon", tags=["kalkulator"])
    def severance(body: SeveranceRequest) -> dict:
        """Severance pay under the rules in force on the dismissal date. No model is involved:
        the rules are data, and each line names the articles it rests on."""
        return service.severance(
            body.tanggal_mulai,
            body.tanggal_phk,
            body.upah_bulanan,
            body.alasan,
            leave_days=body.sisa_cuti_hari,
            days_per_week=body.hari_kerja_per_minggu,
            micro_or_small=body.usaha_mikro_kecil,
        )

    @app.post("/calc/kompensasi-pkwt", tags=["kalkulator"])
    def compensation(body: CompensationRequest) -> dict:
        """Compensation when a fixed-term contract (PKWT) ends."""
        return service.pkwt_compensation(
            body.tanggal_mulai,
            body.tanggal_berakhir,
            body.upah_bulanan,
            micro_or_small=body.usaha_mikro_kecil,
        )

    if ui:
        from pasalkini.ui.app import PATH, mount

        @app.get("/", include_in_schema=False)
        def home() -> RedirectResponse:
            return RedirectResponse(f"{PATH}/")

        app = mount(app, service)
    return app

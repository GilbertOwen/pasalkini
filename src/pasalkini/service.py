"""What the app does, behind both the API and the UI: answer a question, show an article as it
stood on a date, show its history, show a law as it stood, compute severance.

Loaded once: the dated corpus, the search indexes, the answer pipeline and the article versions.
Only `ask` needs the language model. The other four read the temporal model or the calculator's
rules, and keep working when Ollama is not running.

`ask` is where the app's own rules live, around the pipeline:
- the question is redacted before anything about it is kept (log, trace);
- an answer already given for the same question, date, law and code comes from the cache, unless
  personal data was found in the question;
- one question is answered at a time: there is one GPU;
- a model server that does not answer is reported as such (ModelUnavailable), not as a crash.
"""

import hashlib
import logging
import os
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date

import httpx
import numpy as np
import ollama

from pasalkini import __version__
from pasalkini.answer.calculate import Calculation
from pasalkini.answer.context import (
    Library,
    history_of,
    instrument_label,
    label,
    merge_periods,
    notes_of,
    rulings_read,
)
from pasalkini.answer.llm import chat_json
from pasalkini.answer.pipeline import DATE_SOURCES, Outcome, Pipeline
from pasalkini.answer.understand import Chat, decide_date
from pasalkini.answer.verify import Passage, body_of
from pasalkini.cache import AnswerCache, answer_key, code_fingerprint
from pasalkini.corpus import short_name
from pasalkini.pipelines import CONFIGS, PipelineConfig, load_chunks
from pasalkini.privacy.log import QuestionLog
from pasalkini.privacy.redact import redact
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.lexical import BM25Index
from pasalkini.sources import Manifest, load_manifest, load_topics
from pasalkini.temporal.corpus import DatedChunk, instrument_name
from pasalkini.temporal.model import Version
from pasalkini.temporal.query import (
    article_sort_key,
    consolidate,
    diff_segments,
    format_date,
    history,
    validity,
)
from pasalkini.temporal.rulings import abbreviate
from pasalkini.temporal.store import load_versions
from pasalkini.tools.pesangon import (
    Result,
    hitung_kompensasi_pkwt,
    hitung_pesangon,
    reasons_on,
)
from pasalkini.trace import Exporter, Span, Trace, tracing

logger = logging.getLogger("pasalkini")

MAX_QUESTION_CHARS = 2000
TRACE_ENDPOINT = "PASALKINI_TRACE_ENDPOINT"  # e.g. http://localhost:6006/v1/traces (Phoenix)
MODEL_ERRORS = (httpx.HTTPError, ollama.ResponseError, ConnectionError)

# The pipeline's stages, as told to a waiting user.
STAGES = {
    "embed": "Menyiapkan pencarian",
    "understand": "Memahami pertanyaan",
    "calculate": "Menghitung",
    "retrieve": "Mencari pasal yang berlaku pada tanggal itu",
    "select": "Memilih dan memeriksa kutipan",
    "answer": "Menulis dan memeriksa jawaban",
    "select again": "Memilih kutipan lain",
    "later law": "Mencari aturan yang baru berlaku kemudian",
}
# The API speaks the answer contract of PLAN.md; the pipeline's own labels are Indonesian.
INTENTS = {
    "jelaskan": "explain",
    "status": "status",
    "riwayat": "history",
    "hitung": "calculate",
    "di_luar_cakupan": "out_of_scope",
}
AS_OF_SOURCES = {"pertanyaan": "question", "pemilih_tanggal": "date_picker", "hari_ini": "today"}
CONFIDENCE = {"tinggi": "high", "sedang": "medium", "rendah": "low"}
STATUS_WORDS = {"in_force": "berlaku", "conditional": "berlaku bersyarat", "repealed": "dihapus"}


class ModelUnavailable(RuntimeError):
    """The local model server did not answer, or does not have the model."""


def passage_dict(passage: Passage) -> dict:
    chunk = passage.chunk
    found = {
        "source_id": chunk.source_id,
        # What to ask /provisions for, to read the whole article as it stood on a date.
        "provision_id": getattr(chunk, "provision_id", chunk.source_id),
        "title": chunk.title,
        "quote": passage.quote,
    }
    if isinstance(chunk, DatedChunk):
        found["valid_from"] = chunk.valid_from.isoformat()
        found["valid_to"] = chunk.valid_to.isoformat() if chunk.valid_to else None
    return found


def result_dict(result: Result) -> dict:
    """A calculator result as JSON: one line per component, each with the articles it rests on."""
    amounts = [line.amount for line in result.lines if line.amount is not None]
    return {
        "regime": result.regime,
        "service": result.service,
        "reason": result.reason,
        "lines": [
            {
                "component": line.component,
                "formula": line.formula,
                "amount": line.amount,
                "months_of_wage": float(line.months) if line.months is not None else None,
                "basis": [b.strip() for b in line.basis.split(";") if b.strip()],
            }
            for line in result.lines
        ],
        "total": sum(amounts) if amounts else None,
        "total_months_of_wage": float(result.total_months) or None,
        "minimum": result.minimum,
        "other_reasons_same_article": result.variants,
        "notes": result.notes,
        "unsupported": result.unsupported,
    }


def calculation_dict(calculation: Calculation) -> dict:
    return {
        "kind": calculation.kind,
        "wage": calculation.wage,
        "months": calculation.months,
        "reason_read_from": calculation.evidence,
        "error": calculation.error,
        "text": calculation.text(),
        "result": result_dict(calculation.result) if calculation.result else None,
    }


def answer_payload(outcome: Outcome) -> dict:
    """The answer contract: everything the user is shown, as data."""
    u = outcome.understanding
    passages = [passage_dict(p) for p in outcome.passages]
    return {
        "as_of": u.as_of.isoformat(),
        "as_of_source": AS_OF_SOURCES[u.as_of_source],
        "as_of_text": f"{format_date(u.as_of)} ({DATE_SOURCES[u.as_of_source]})",
        "intent": INTENTS.get(u.intent, u.intent),
        "answer": outcome.answer,
        "abstained": outcome.abstained,
        "confidence": CONFIDENCE.get(outcome.confidence, outcome.confidence),
        "citations": passages if outcome.citations else [],
        # Found, but the model saw no answer in them: shown as the nearest passages, not as
        # the basis of an answer.
        "nearest": [] if outcome.citations else passages,
        "later": [passage_dict(p) for p in outcome.later],  # began after the date
        "calculation": calculation_dict(outcome.calculation) if outcome.calculation else None,
        "timeline": outcome.timeline,
        "changed_since": outcome.changed_since,
        "caveats": outcome.caveats,
        "referral": outcome.referral,
        "looked_up": bool(outcome.context),  # False for a refusal: nothing was searched
        "seconds": outcome.seconds,
        "cached": False,
    }


def version_dict(version: Version, previous: Version | None) -> dict:
    changed = previous is not None and previous.text != version.text
    return {
        "version_id": version.version_id,
        "source_id": version.source_id,
        "published_in": instrument_label(version.source_id),
        "status": version.status,
        "valid_from": version.valid_from.isoformat(),
        "valid_to": version.valid_to.isoformat() if version.valid_to else None,
        "validity": validity(version),
        "text": version.text,
        "rulings": version.rulings,
        # Rulings and status changes, with a ruling's long citations shortened. A deletion's
        # own instruction is its text already.
        "notes": [
            abbreviate(note) if "/amar-" in note else note
            for note in version.notes
            if note.startswith("[")
        ],
        "same_text_as_previous": previous is not None and not changed,
        # Word-level changes from the version before: [text, '+' | '-' | null].
        "diff": diff_segments(previous.text, version.text) if changed else None,
    }


class Service:
    def __init__(
        self,
        pipeline: Pipeline,
        versions: list[Version],
        manifest: Manifest,
        *,
        embed: Callable[[str], np.ndarray] | None = None,
        cache: AnswerCache | None = None,
        log: QuestionLog | None = None,
        exporter: Exporter | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.pipeline = pipeline
        self.config: PipelineConfig = pipeline.config
        self.library: Library = pipeline.library
        self.versions = versions
        self.manifest = manifest
        self.embed = embed or self.embed_on_cpu
        self.cache = cache
        self.log = log
        self.exporter = exporter
        self.today = today
        self.lock = threading.Lock()
        self.chunks: list[DatedChunk] = [c for cs in self.library.by_source.values() for c in cs]
        self.names = {i.id: short_name(i) for i in manifest.instruments if i.number}
        settings = self.config.model_dump_json().encode("utf-8")
        self.settings_key = hashlib.sha256(settings).hexdigest()[:16]

    @classmethod
    def load(cls, config_name: str = "pasalkini", chat: Chat = chat_json) -> "Service":
        """Everything from disk. Embeds nothing when the index cache is complete."""
        config = CONFIGS[config_name]
        chunks = load_chunks(config)
        index = DenseIndex.build(
            config.embed_model, chunks, config.embed_num_ctx, with_titles=config.chunk_headers
        )
        lexical = BM25Index(chunks) if config.retriever != "dense" else None
        pipeline = Pipeline(config, chunks, index, lexical, load_topics(), chat=chat)
        endpoint = os.environ.get(TRACE_ENDPOINT)
        return cls(
            pipeline,
            load_versions(),
            load_manifest(),
            cache=AnswerCache(),
            log=QuestionLog(),
            exporter=Exporter(endpoint) if endpoint else None,
        )

    # --- Tanya ---

    def embed_on_cpu(self, question: str) -> np.ndarray:
        # On the CPU the embedding model stays loaded beside the chat model, which the 6 GB GPU
        # cannot do; a query takes about 0.2 s.
        return self.pipeline.index.embed_query(
            question, self.config.query_instruction, self.config.embed_num_ctx, on_cpu=True
        )

    def law_as_of(self, today: date) -> date | None:
        """The last day on which a wording in the corpus took effect."""
        return max((c.valid_from for c in self.chunks if c.valid_from <= today), default=None)

    def ask(
        self,
        question: str,
        date_hint: date | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> dict:
        question = question.strip()
        if not question:
            raise ValueError("Pertanyaan kosong.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValueError(
                f"Pertanyaan terlalu panjang (paling banyak {MAX_QUESTION_CHARS} huruf)."
            )
        redacted = redact(question)
        today = self.today()
        as_of, source = decide_date(question, date_hint, today)
        entry = {
            "question": redacted.text,
            "personal_data": redacted.found,
            "date_picker": date_hint.isoformat() if date_hint else None,
            "as_of": as_of.isoformat(),
            "as_of_source": AS_OF_SOURCES[source],
        }
        # A question with personal data in it is neither stored nor looked up.
        key = None
        if self.cache is not None and redacted.clean:
            fingerprint = self.pipeline.index.fingerprint
            key = answer_key(
                question,
                as_of,
                source,
                fingerprint,
                self.law_as_of(today),
                self.settings_key,
                code_fingerprint(),
            )
            cached = self.cache.get(key)
            if cached is not None:
                payload = {**cached, "cached": True, "seconds": {"total": 0.0}}
                self.record(entry, payload)
                return payload

        def started(span: Span, depth: int) -> None:
            if depth == 1 and on_stage is not None:  # the pipeline's stages, not their model calls
                on_stage(span.name)

        trace = None
        try:
            with self.lock, tracing("ask", started, input=question) as trace:
                self.pipeline.today = today
                outcome = self.pipeline.run(question, date_hint, self.embed(question))
                payload = answer_payload(outcome)
                trace.root.attributes.update(
                    output=payload["answer"],
                    intent=payload["intent"],
                    as_of=payload["as_of"],
                    abstained=payload["abstained"],
                    confidence=payload["confidence"],
                )
        except MODEL_ERRORS as error:
            logger.warning("model call failed: %r", error)
            self.record(entry, None, error=type(error).__name__)
            self.export(trace)
            raise ModelUnavailable(
                "Model bahasa tidak dapat dihubungi. Pastikan Ollama berjalan dan model "
                f"{self.config.chat_model} serta {self.config.embed_model} sudah terpasang."
            ) from error
        self.export(trace)
        if key is not None and outcome.json_ok:
            self.cache.put(key, payload)
        self.record(entry, payload)
        return payload

    def ask_events(
        self, question: str, date_hint: date | None = None
    ) -> Iterator[tuple[str, dict]]:
        """The same as `ask`, as a stream: ('stage', …) as each stage starts, then ('answer', …)
        or ('error', …). The pipeline runs in a thread of its own so that the stages can be
        passed on while it works."""
        events: queue.Queue[tuple[str, dict]] = queue.Queue()

        def stage(name: str) -> None:
            events.put(("stage", {"stage": name, "label": STAGES.get(name, name)}))

        def work() -> None:
            try:
                events.put(("answer", self.ask(question, date_hint, stage)))
            except ValueError as error:
                events.put(("error", {"status": 422, "detail": str(error)}))
            except ModelUnavailable as error:
                events.put(("error", {"status": 503, "detail": str(error)}))
            except Exception:  # the stream has to end whatever happens
                logger.exception("ask failed")
                events.put(("error", {"status": 500, "detail": "Terjadi kesalahan pada aplikasi."}))

        threading.Thread(target=work, daemon=True).start()
        while True:
            kind, data = events.get()
            yield kind, data
            if kind != "stage":
                return

    def record(self, entry: dict, payload: dict | None, error: str | None = None) -> None:
        if self.log is None:
            return
        if payload is not None:
            entry = {
                **entry,
                "intent": payload["intent"],
                "abstained": payload["abstained"],
                "confidence": payload["confidence"],
                "citations": [c["source_id"] for c in payload["citations"]],
                "seconds": payload["seconds"],
                "cached": payload["cached"],
            }
        self.log.write({**entry, "error": error})

    def export(self, trace: Trace | None) -> None:
        if self.exporter is None or trace is None:
            return
        try:
            self.exporter.export(trace)
        except Exception:  # tracing must never break an answer
            logger.exception("trace export failed")

    # --- Riwayat Pasal, Konsolidasi ---

    def name(self, instrument_id: str) -> str:
        return instrument_name(instrument_id, self.names)

    def instruments(self) -> list[dict]:
        """The laws and regulations that have articles in the temporal model, in manifest order,
        then the laws amended by Cipta Kerja that are not in the manifest."""
        articles: dict[str, set[str]] = {}
        for version in self.versions:
            articles.setdefault(version.instrument_id, set()).add(version.provision_id)
        order = [i.id for i in self.manifest.instruments if i.id in articles]
        order += sorted(set(articles) - set(order))
        known = {i.id: i for i in self.manifest.instruments}
        found = []
        for instrument_id in order:
            instrument = known.get(instrument_id)
            found.append(
                {
                    "id": instrument_id,
                    "name": self.name(instrument_id),
                    "title": instrument.title if instrument else None,
                    "articles": len(articles[instrument_id]),
                    "in_force_on": (
                        instrument.in_force_on.isoformat()
                        if instrument and instrument.in_force_on
                        else None
                    ),
                    "official_urls": (
                        {name: str(url) for name, url in instrument.urls.items()}
                        if instrument
                        else {}
                    ),
                }
            )
        return found

    def articles(self, instrument_id: str) -> list[dict]:
        """Every article the instrument ever had, in article order."""
        labels = {
            v.provision_id: v.label for v in self.versions if v.instrument_id == instrument_id
        }
        return [
            {"provision_id": provision_id, "label": labels[provision_id]}
            for provision_id in sorted(labels, key=article_sort_key)
        ]

    def provision(self, provision_id: str, as_of: date) -> dict | None:
        """One article, or one ruling point, as it stood on the date. None when PasalKini does
        not have it at all."""
        every = self.library.by_provision.get(provision_id)
        if not every:
            return None
        base = {
            "provision_id": provision_id,
            "label": label(every[0]),
            "as_of": as_of.isoformat(),
        }
        current = self.library.versions(provision_id, as_of, history=False)
        if not current:
            return {
                **base,
                "exists_on_date": False,
                "first_valid_from": every[0].valid_from.isoformat(),
                "message": (
                    f"{label(every[0])} belum berlaku pada {format_date(as_of)}; versi pertama "
                    f"dalam sumber PasalKini berlaku sejak {format_date(every[0].valid_from)}."
                ),
            }
        chunk = merge_periods(self.library.periods(current[0], as_of))
        return {
            **base,
            "exists_on_date": True,
            "title": chunk.title,
            "status": chunk.status,
            "status_text": STATUS_WORDS[chunk.status],
            "valid_from": chunk.valid_from.isoformat(),
            "valid_to": chunk.valid_to.isoformat() if chunk.valid_to else None,
            "source_id": chunk.source_id,
            "published_in": self.library.instrument(chunk.source_id, as_of),
            "text": body_of(chunk),
            "notes": [{"id": note_id, "text": text} for note_id, text in notes_of(chunk)],
            # What the Constitutional Court's rulings on this wording mean, read out by rule.
            "rulings_read": rulings_read(self.library, chunk, set()),
        }

    def history(self, provision_id: str) -> dict | None:
        """Every version of one article with what changed between them, and its timeline as
        code states it."""
        versions = history(self.versions, provision_id)
        if not versions:
            return None
        previous = [None, *versions[:-1]]
        return {
            "provision_id": provision_id,
            "label": f"{self.name(versions[0].instrument_id)} {versions[0].label}",
            "timeline": history_of(self.library, provision_id, self.today()),
            "versions": [
                version_dict(v, before) for v, before in zip(versions, previous, strict=True)
            ],
        }

    def law(self, instrument_id: str, as_of: date, only: list[str] | None = None) -> dict | None:
        """The instrument's articles as they stood on the date. `only`: article numbers."""
        if not any(v.instrument_id == instrument_id for v in self.versions):
            return None
        articles = consolidate(self.versions, instrument_id, as_of)
        if only:
            wanted = {f"{instrument_id}/pasal-{number.strip().lower()}" for number in only}
            articles = [v for v in articles if v.provision_id in wanted]
        return {
            "instrument_id": instrument_id,
            "name": self.name(instrument_id),
            "as_of": as_of.isoformat(),
            "articles": [
                {
                    "provision_id": v.provision_id,
                    "label": v.label,
                    "status": v.status,
                    "validity": validity(v),
                    "source_id": v.source_id,
                    "amended": v.source_id.split("/")[0] != instrument_id,
                    "text": v.text,
                    "rulings": v.rulings,
                }
                for v in articles
            ],
        }

    # --- Kalkulator ---

    def reasons(self, day: date) -> dict[str, str]:
        """Dismissal reasons under the rules in force on the day: code → description."""
        return reasons_on(day)

    def cited(self, result: dict, day: date) -> dict:
        """Add the articles the amounts rest on, as they are titled on the day."""
        ids = list(dict.fromkeys(b for line in result["lines"] for b in line["basis"]))
        sources = []
        for source_id in ids:
            chunk = self.library.source_on(source_id, day)
            title = chunk.title if chunk else source_id
            provision = chunk.provision_id if chunk else source_id
            sources.append({"source_id": source_id, "provision_id": provision, "title": title})
        return {**result, "as_of": day.isoformat(), "sources": sources}

    def severance(
        self,
        start: date | None,
        end: date,
        wage: int | None,
        reason: str,
        *,
        leave_days: int = 0,
        days_per_week: int = 5,
        micro_or_small: bool = False,
    ) -> dict:
        result = hitung_pesangon(
            start,
            end,
            wage,
            reason,
            sisa_cuti_hari=leave_days,
            hari_kerja_per_minggu=days_per_week,
            usaha_mikro_kecil=micro_or_small,
        )
        return self.cited(result_dict(result), end)

    def pkwt_compensation(
        self, start: date, end: date, wage: int | None, *, micro_or_small: bool = False
    ) -> dict:
        result = hitung_kompensasi_pkwt(start, end, wage, usaha_mikro_kecil=micro_or_small)
        return self.cited(result_dict(result), end)

    # --- Health ---

    def health(self) -> dict:
        wanted = {"chat": self.config.chat_model, "embedding": self.config.embed_model}
        started = time.perf_counter()
        try:
            installed = {m.model for m in ollama.Client(timeout=3).list().models}
            model = {
                "reachable": True,
                **{role: {"name": n, "installed": n in installed} for role, n in wanted.items()},
            }
        except MODEL_ERRORS as error:
            model = {"reachable": False, "error": type(error).__name__}
        ready = model["reachable"] and all(model[role]["installed"] for role in wanted)
        today = self.today()
        law_as_of = self.law_as_of(today)
        return {
            # 'degraded': the article history, the consolidated law and the calculator work;
            # questions do not.
            "status": "ok" if ready else "degraded",
            "version": __version__,
            "today": today.isoformat(),
            "corpus": {
                "chunks": len(self.chunks),
                "article_versions": len(self.versions),
                "fingerprint": self.pipeline.index.fingerprint,
                "law_as_of": law_as_of.isoformat() if law_as_of else None,
            },
            "model": model,
            "cache_entries": len(self.cache) if self.cache is not None else None,
            "tracing": self.exporter.endpoint if self.exporter is not None else None,
            "checked_in_seconds": round(time.perf_counter() - started, 2),
        }

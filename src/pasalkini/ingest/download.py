"""Polite downloader for the PDFs listed in sources/manifest.yaml.

Rules (from the legal review):
- respect robots.txt, fetched with our own User-Agent;
- at most one request every DELAY_SECONDS, over one connection;
- a User-Agent that names the project;
- download each document once; record URL, time, size and SHA-256 in sources/downloads.lock.json;
- never log in, solve CAPTCHAs or call hidden APIs.

Note: peraturan.bpk.go.id answers 403 to Python's default User-Agent, so
urllib.robotparser.RobotFileParser.read() would wrongly treat the whole site as disallowed.
We fetch robots.txt ourselves and hand the text to the parser.
"""

import hashlib
import json
import os
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from pasalkini.paths import RAW_DIR, SOURCES_DIR
from pasalkini.sources import Instrument, load_manifest

LOCK_PATH = SOURCES_DIR / "downloads.lock.json"
DELAY_SECONDS = 3.0
TIMEOUT_SECONDS = 180.0


def user_agent() -> str:
    contact = os.environ.get("PASALKINI_CONTACT", "https://github.com/GilbertOwen/pasalkini")
    return f"PasalKini/0.1 (+{contact}; legal research project, rate-limited)"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_path(instrument_id: str, part: str = "main") -> Path:
    """data/raw/<id>.pdf for the main file, data/raw/<id>.penjelasan.pdf for a separate one."""
    suffix = "" if part == "main" else f".{part}"
    return RAW_DIR / f"{instrument_id}{suffix}.pdf"


def files_of(instrument: Instrument) -> list[tuple[str, str]]:
    """(part, url) pairs to download for an instrument."""
    files = [("main", str(instrument.pdf_url))]
    if instrument.penjelasan_pdf_url:
        files.append(("penjelasan", str(instrument.penjelasan_pdf_url)))
    return files


def load_lock() -> dict:
    if LOCK_PATH.exists():
        return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    return {}


def save_lock(lock: dict) -> None:
    ordered = dict(sorted(lock.items()))
    LOCK_PATH.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class Result:
    key: str  # '<id>' or '<id>.penjelasan'
    status: str  # downloaded | unchanged | changed | skipped | error
    detail: str = ""


class PoliteClient:
    """One HTTP client, one request at a time, robots.txt checked per host."""

    def __init__(self, delay: float = DELAY_SECONDS) -> None:
        self.delay = delay
        self.client = httpx.Client(
            headers={"User-Agent": user_agent()},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def _get(self, url: str) -> httpx.Response:
        self._wait()
        return self.client.get(url)

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            response = self._get(f"{host}/robots.txt")
            if response.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(response.text.splitlines())
                self._robots[host] = parser
            elif response.status_code == 404:
                self._robots[host] = None  # no robots.txt: nothing is disallowed
            else:
                raise RuntimeError(f"robots.txt at {host} returned {response.status_code}")
        parser = self._robots[host]
        return parser is None or parser.can_fetch(user_agent(), url)

    def fetch_pdf(self, url: str) -> bytes:
        response = self._get(url)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"not a PDF (content-type {response.headers.get('content-type')})")
        return response.content

    def close(self) -> None:
        self.client.close()


def download_one(
    client: PoliteClient, instrument_id: str, part: str, url: str, lock: dict, force: bool
) -> Result:
    key = instrument_id if part == "main" else f"{instrument_id}.{part}"
    target = raw_path(instrument_id, part)
    recorded = lock.get(key)

    if (
        not force
        and target.exists()
        and recorded
        and recorded["url"] == url
        and recorded["sha256"] == sha256_of(target)
    ):
        return Result(key, "unchanged", "already downloaded; no request made")

    if not client.allowed(url):
        return Result(key, "skipped", "disallowed by robots.txt")

    try:
        content = client.fetch_pdf(url)
    except (httpx.HTTPError, ValueError) as exc:
        return Result(key, "error", str(exc))

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    status = "downloaded"
    detail = f"{len(content) / 1e6:.1f} MB"
    if recorded and recorded["url"] == url and recorded["sha256"] != digest:
        status = "changed"
        detail += f"; the source file changed since {recorded['retrieved_at']}"

    lock[key] = {
        "url": url,
        "sha256": digest,
        "bytes": len(content),
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return Result(key, status, detail)


def download_all(only: list[str] | None = None, force: bool = False) -> list[Result]:
    manifest = load_manifest()
    lock = load_lock()
    client = PoliteClient()
    results = []
    try:
        for instrument in manifest.instruments:
            if instrument.status != "active" or instrument.pdf_url is None:
                continue
            if only and instrument.id not in only:
                continue
            for part, url in files_of(instrument):
                result = download_one(client, instrument.id, part, url, lock, force)
                results.append(result)
                print(f"  {result.key:<32} {result.status:<11} {result.detail}", flush=True)
                save_lock(lock)  # save after each file so an interrupted run keeps its progress
    finally:
        client.close()
    return results

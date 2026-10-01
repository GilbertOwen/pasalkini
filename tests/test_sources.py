import pytest
from pydantic import ValidationError

from pasalkini.sources import Instrument, Topics, load_manifest, load_topics


@pytest.fixture(scope="module")
def manifest():
    return load_manifest()


def test_manifest_loads_with_unique_ids(manifest):
    assert len(manifest.instruments) >= 9
    assert len(manifest.ids()) == len(manifest.instruments)


def test_core_chain_is_present(manifest):
    core = {
        "uu-13-2003",
        "uu-11-2020",
        "perppu-2-2022",
        "uu-6-2023",
        "mk-168-puu-xxi-2023",
        "pp-35-2021",
        "pp-36-2021",
    }
    assert core <= manifest.ids()


def test_active_sources_are_official(manifest):
    official_hosts = {
        "peraturan.bpk.go.id",
        "peraturan.go.id",
        "www.peraturan.go.id",
        "www.mkri.id",
        "jdih.kemnaker.go.id",
    }
    for instrument in manifest.instruments:
        files = [instrument.pdf_url, instrument.penjelasan_pdf_url]
        urls = list(instrument.urls.values()) + [u for u in files if u]
        for url in urls:
            assert url.host in official_hosts, f"{instrument.id}: {url} is not an official source"


def test_manifest_dates_verified(manifest):
    todo = [i.id for i in manifest.instruments if i.status == "active" and not i.dates_verified]
    if todo:
        pytest.skip(f"dates still to verify from the documents: {', '.join(todo)}")


def test_active_instrument_needs_number():
    with pytest.raises(ValidationError):
        Instrument(
            id="uu-1-2000",
            kind="UU",
            number=None,
            year=2000,
            title="Contoh",
            status="active",
            parse_scope="all",
            urls={"bpk": "https://peraturan.bpk.go.id/Details/1"},
        )


def test_verified_dates_are_required():
    with pytest.raises(ValidationError):
        Instrument(
            id="pp-1-2000",
            kind="PP",
            number="1",
            year=2000,
            title="Contoh",
            status="active",
            parse_scope="all",
            urls={"bpk": "https://peraturan.bpk.go.id/Details/1"},
            dates_verified=True,
        )


def test_topics_load():
    topics = load_topics()
    assert {"pkwt", "alih-daya", "pesangon", "phk", "upah"} <= topics.ids()


def test_duplicate_synonym_rejected():
    with pytest.raises(ValidationError):
        Topics.model_validate(
            {
                "topics": [
                    {"id": "a", "name": "A", "description": "a", "synonyms": ["kontrak"]},
                    {"id": "b", "name": "B", "description": "b", "synonyms": ["kontrak"]},
                ]
            }
        )


def test_uu_6_2023_is_linked_to_the_perppu_it_enacted(manifest):
    assert manifest.get("uu-6-2023").enacts == "perppu-2-2022"

"""Models and loaders for sources/manifest.yaml and sources/topics.yaml."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from pasalkini.paths import MANIFEST_PATH, TOPICS_PATH

# Instrument ids look like 'uu-13-2003' or 'mk-168-puu-xxi-2023'.
INSTRUMENT_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class Kind(StrEnum):
    UU = "UU"
    PERPPU = "PERPPU"
    PP = "PP"
    PERMEN = "PERMEN"
    PUTUSAN_MK = "PUTUSAN_MK"


class Instrument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=INSTRUMENT_ID_PATTERN)
    kind: Kind
    number: str | None
    year: int | None = Field(default=None, ge=1945, le=2100)
    title: str = Field(min_length=3)
    status: Literal["active", "pending"]
    parse_scope: str
    urls: dict[str, HttpUrl]
    approved_on: date | None = None
    promulgated_on: date | None = None
    in_force_on: date | None = None
    dates_verified: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def check_consistency(self) -> "Instrument":
        if self.status == "active":
            if self.number is None or self.year is None:
                raise ValueError(f"{self.id}: an active instrument needs a number and a year")
            if not self.urls:
                raise ValueError(f"{self.id}: an active instrument needs at least one official URL")
        if self.dates_verified and (self.promulgated_on is None or self.in_force_on is None):
            raise ValueError(f"{self.id}: dates_verified is true but dates are missing")
        if self.kind is Kind.UU and self.dates_verified and self.approved_on is None:
            raise ValueError(f"{self.id}: a verified UU needs approved_on")
        if self.promulgated_on and self.in_force_on and self.in_force_on < self.promulgated_on:
            raise ValueError(f"{self.id}: in_force_on is before promulgated_on")
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruments: list[Instrument]

    @model_validator(mode="after")
    def check_unique_ids(self) -> "Manifest":
        ids = [i.id for i in self.instruments]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate instrument ids: {sorted(duplicates)}")
        return self

    def ids(self) -> set[str]:
        return {i.id for i in self.instruments}

    def get(self, instrument_id: str) -> Instrument:
        for instrument in self.instruments:
            if instrument.id == instrument_id:
                return instrument
        raise KeyError(instrument_id)


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=INSTRUMENT_ID_PATTERN)
    name: str
    description: str
    synonyms: list[str]


class Topics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[Topic]

    @model_validator(mode="after")
    def check_unique(self) -> "Topics":
        ids = [t.id for t in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate topic ids")
        seen: dict[str, str] = {}
        for topic in self.topics:
            for synonym in topic.synonyms:
                if synonym != synonym.lower():
                    raise ValueError(f"synonym '{synonym}' in {topic.id} must be lower-case")
                if synonym in seen:
                    raise ValueError(
                        f"synonym '{synonym}' is used by both {seen[synonym]} and {topic.id}"
                    )
                seen[synonym] = topic.id
        return self

    def ids(self) -> set[str]:
        return {t.id for t in self.topics}


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_manifest(path: Path = MANIFEST_PATH) -> Manifest:
    return Manifest.model_validate(_read_yaml(path))


def load_topics(path: Path = TOPICS_PATH) -> Topics:
    return Topics.model_validate(_read_yaml(path))

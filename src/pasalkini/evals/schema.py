"""Schema for evals/datasets/golden.jsonl.

Expected answers are written as *source IDs*: where a piece of legal text was published.

    uu-13-2003/pasal-59                the original wording of Pasal 59
    perppu-2-2022/pasal-81/angka-15    a point in Pasal 81 that re-words an article
    uu-11-2020                         anything published in that instrument

Source IDs exist from Phase 1, before the temporal model, so labels written now stay valid.
"""

import json
import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from pasalkini.paths import GOLDEN_PATH

ITEM_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
SOURCE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*$"


class Category(StrEnum):
    STABLE_RULE = "stable_rule"
    TEMPORAL_TRAP = "temporal_trap"
    STATUS = "status"
    WHAT_CHANGED = "what_changed"
    CALCULATION = "calculation"
    DATE_EXTRACTION = "date_extraction"
    SHOULD_ABSTAIN = "should_abstain"
    ADVERSARIAL = "adversarial"


class EvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ITEM_ID_PATTERN)
    pair_id: str | None = Field(default=None, pattern=ITEM_ID_PATTERN)
    question: str = Field(min_length=10)
    as_of: date
    # True when the date is only in the question text and must be extracted;
    # False when it would come from the date picker.
    date_in_question: bool = False
    category: Category
    topic: str | None
    expected_sources: list[str] = []
    must_not_cite: list[str] = []
    expected_points: list[str] = []
    should_abstain: bool = False
    source: Literal["human", "synthetic_verified", "draft"]
    split: Literal["dev", "test"]
    review: Literal["needed", "done"]
    notes: str = ""

    @model_validator(mode="after")
    def check_consistency(self) -> "EvalItem":
        for sid in self.expected_sources + self.must_not_cite:
            if not re.match(SOURCE_ID_PATTERN, sid):
                raise ValueError(f"{self.id}: bad source id '{sid}'")
        overlap = set(self.expected_sources) & set(self.must_not_cite)
        if overlap:
            raise ValueError(f"{self.id}: {sorted(overlap)} is both expected and forbidden")
        if self.category is Category.SHOULD_ABSTAIN and not self.should_abstain:
            raise ValueError(f"{self.id}: should_abstain items must set should_abstain: true")
        if self.category is Category.TEMPORAL_TRAP and self.pair_id is None:
            raise ValueError(f"{self.id}: temporal traps need a pair_id")
        if self.review == "done":
            if self.source == "draft":
                raise ValueError(f"{self.id}: reviewed items can't have source 'draft'")
            if not self.expected_points:
                raise ValueError(f"{self.id}: reviewed items need expected_points")
            if not self.should_abstain and not self.expected_sources:
                raise ValueError(f"{self.id}: reviewed items need expected_sources")
        return self

    def cited_instruments(self) -> set[str]:
        """Instrument ids referenced by expected_sources and must_not_cite."""
        return {sid.split("/")[0] for sid in self.expected_sources + self.must_not_cite}


class GoldenFileError(ValueError):
    pass


def load_golden(path: Path = GOLDEN_PATH) -> list[EvalItem]:
    """Load the JSONL file; errors name the line number."""
    items: list[EvalItem] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                items.append(EvalItem.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise GoldenFileError(f"{path.name} line {line_number}: {exc}") from exc
    return items

"""Events are the source of truth; versions are rebuilt from them (event sourcing)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Op = Literal[
    "enact",  # an article of a base instrument takes effect
    "amend",  # new wording of an existing article
    "insert",  # a new article (e.g. Pasal 61A)
    "delete",  # 'Pasal X dihapus.'
    "interpret",  # an MK ruling conditions the meaning of an article
    "revoke_instrument",  # a whole instrument stops applying (Perppu 2/2022 revoking UU 11/2020)
    "conditional_instrument",  # everything published in an instrument becomes conditional
]
Status = Literal["in_force", "conditional", "repealed"]


class Event(BaseModel):
    id: str
    op: Op
    effective_on: date
    source_id: str  # where the change was published: 'uu-11-2020/pasal-81/angka-15'
    target: str  # a provision ('uu-13-2003/pasal-59') or, for *_instrument ops, instruments
    label: str | None = None  # 'Pasal 59'
    text: str | None = None  # the new wording, for enact / amend / insert
    note: str = ""  # the instruction or ruling text
    order: int = 0  # tie-break for events on the same date: lower runs first


class Version(BaseModel):
    version_id: str
    provision_id: str  # stable identity of the article across time
    label: str
    source_id: str  # where this wording was published
    text: str
    valid_from: date
    valid_to: date | None = None  # None: still applies
    status: Status
    rulings: list[str] = []  # MK ruling points that condition this version
    notes: list[str] = []

    def valid_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day < self.valid_to)

    @property
    def instrument_id(self) -> str:
        return self.provision_id.split("/")[0]

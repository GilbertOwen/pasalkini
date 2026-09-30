"""Replay events in date order to build every article's versions.

Rules:
- amend / insert: the current version ends the day the change takes effect; a new one starts.
- delete: the article is replaced by a 'repealed' version saying it was deleted.
- interpret (MK ruling): same wording, status 'conditional', ruling attached.
- revoke_instrument: every version published in that instrument ends; the wording it had
  replaced applies again (unless another change the same day replaces it too).
- conditional_instrument: every version published in that instrument becomes 'conditional'.
- A version that would last zero days (replaced the day it started) is dropped.
"""

from collections import defaultdict
from datetime import date

from pasalkini.temporal.model import Event, Status, Version


class VersionBuilder:
    def __init__(self) -> None:
        self.open: dict[str, Version] = {}
        self.history: dict[str, list[Version]] = defaultdict(list)
        self.warnings: list[str] = []
        self._ids: set[str] = set()

    # ---------------------------------------------------------------- primitives

    def _close(self, pid: str, day: date) -> Version | None:
        version = self.open.pop(pid, None)
        if version is None:
            return None
        if version.valid_from >= day:  # zero-length: replaced the day it started
            self.history[pid].remove(version)
            self._ids.discard(version.version_id)
        else:
            version.valid_to = day
        return version

    def _open(self, pid: str, day: date, **fields) -> Version:
        base = f"{pid}@{day.isoformat()}"
        version_id, n = base, 1
        while version_id in self._ids:
            n += 1
            version_id = f"{base}#{n}"
        self._ids.add(version_id)
        version = Version(version_id=version_id, provision_id=pid, valid_from=day, **fields)
        self.open[pid] = version
        self.history[pid].append(version)
        return version

    def _replace(self, pid: str, day: date, *, status: Status = "in_force", **fields) -> Version:
        self._close(pid, day)
        return self._open(pid, day, status=status, **fields)

    # ---------------------------------------------------------------- events

    def apply(self, event: Event) -> None:
        handler = getattr(self, f"_on_{event.op}")
        handler(event)

    def _on_enact(self, e: Event) -> None:
        if e.target in self.open:
            self.warnings.append(f"{e.id}: enacted twice; treated as an amendment")
        self._replace(e.target, e.effective_on, label=e.label, source_id=e.source_id, text=e.text)

    def _on_amend(self, e: Event) -> None:
        current = self.open.get(e.target)
        if current is None or current.status == "repealed":
            self.warnings.append(
                f"{e.id}: amends an article that does not exist; treated as insert"
            )
        self._replace(e.target, e.effective_on, label=e.label, source_id=e.source_id, text=e.text)

    def _on_insert(self, e: Event) -> None:
        current = self.open.get(e.target)
        if current is not None and current.status != "repealed":
            self.warnings.append(f"{e.id}: inserts an article that already exists; replaced it")
        self._replace(e.target, e.effective_on, label=e.label, source_id=e.source_id, text=e.text)

    def _on_delete(self, e: Event) -> None:
        current = self.open.get(e.target)
        if current is None or current.status == "repealed":
            self.warnings.append(f"{e.id}: deletes an article that does not exist")
            return
        self._replace(
            e.target,
            e.effective_on,
            status="repealed",
            label=current.label,
            source_id=e.source_id,
            text=f"{current.label} dihapus.",
            notes=[e.note],
        )

    def _on_interpret(self, e: Event) -> None:
        current = self.open.get(e.target)
        if current is None or current.status == "repealed":
            self.warnings.append(f"{e.id}: ruling on an article that is not in force")
            return
        self._replace(
            e.target,
            e.effective_on,
            status="conditional",
            label=current.label,
            source_id=current.source_id,
            text=current.text,
            rulings=[*current.rulings, e.source_id],
            notes=[*current.notes, f"[{e.source_id}] {e.note}"],
        )

    def _on_revoke_instrument(self, e: Event) -> None:
        revoked = e.target
        for pid, current in list(self.open.items()):
            if not _published_in(current, revoked):
                continue
            earlier = [v for v in self.history[pid] if not _published_in(v, revoked)]
            self._close(pid, e.effective_on)
            if earlier:  # the wording that the revoked instrument had replaced applies again
                previous = earlier[-1]
                self._open(
                    pid,
                    e.effective_on,
                    status=previous.status,
                    label=previous.label,
                    source_id=previous.source_id,
                    text=previous.text,
                    rulings=previous.rulings,
                    notes=[*previous.notes, f"[{e.source_id}] {e.note}"],
                )

    def _on_conditional_instrument(self, e: Event) -> None:
        targets = e.target.split(",")
        for pid, current in list(self.open.items()):
            if current.status != "in_force" or not any(_published_in(current, t) for t in targets):
                continue
            self._replace(
                pid,
                e.effective_on,
                status="conditional",
                label=current.label,
                source_id=current.source_id,
                text=current.text,
                rulings=[*current.rulings, e.source_id],
                notes=[*current.notes, f"[{e.source_id}] {e.note}"],
            )

    def versions(self) -> list[Version]:
        return [v for versions in self.history.values() for v in versions]


def _published_in(version: Version, instrument_id: str) -> bool:
    return version.source_id == instrument_id or version.source_id.startswith(instrument_id + "/")


def build_versions(events: list[Event]) -> tuple[list[Version], list[str]]:
    builder = VersionBuilder()
    for event in sorted(events, key=lambda e: (e.effective_on, e.order, e.id)):
        builder.apply(event)
    return builder.versions(), builder.warnings

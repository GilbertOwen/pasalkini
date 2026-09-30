"""Rules of the version builder, on hand-made events (no data needed)."""

from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from pasalkini.temporal.build import build_versions
from pasalkini.temporal.model import Event, Version

D0, D1, D2, D3 = date(2003, 3, 25), date(2020, 11, 2), date(2022, 12, 30), date(2024, 10, 31)


def ev(op, day, target, source, text=None, order=0, label="Pasal 1", note="") -> Event:
    return Event(
        id=f"{source}:{op}:{target}",
        op=op,
        effective_on=day,
        source_id=source,
        target=target,
        label=label,
        text=text,
        order=order,
        note=note,
    )


def on(versions: list[Version], pid: str, day: date) -> Version | None:
    found = [v for v in versions if v.provision_id == pid and v.valid_on(day)]
    assert len(found) <= 1, f"overlapping versions of {pid} on {day}"
    return found[0] if found else None


BASE = ev("enact", D0, "uu-1/pasal-1", "uu-1/pasal-1", "asli")


def test_amendment_ends_the_old_version_the_day_the_new_one_starts():
    versions, warnings = build_versions(
        [BASE, ev("amend", D1, "uu-1/pasal-1", "uu-2/pasal-9/angka-1", "baru")]
    )
    assert on(versions, "uu-1/pasal-1", D1 - timedelta(days=1)).text == "asli"
    new = on(versions, "uu-1/pasal-1", D1)
    assert (new.text, new.source_id, new.status) == ("baru", "uu-2/pasal-9/angka-1", "in_force")
    assert warnings == []


def test_deletion_leaves_a_repealed_version():
    versions, _ = build_versions([BASE, ev("delete", D1, "uu-1/pasal-1", "uu-2/pasal-9/angka-2")])
    deleted = on(versions, "uu-1/pasal-1", D1)
    assert deleted.status == "repealed" and deleted.text == "Pasal 1 dihapus."


def test_revocation_restores_the_replaced_wording():
    events = [
        BASE,
        ev("amend", D1, "uu-1/pasal-1", "uu-2/pasal-9/angka-1", "versi uu-2"),
        ev("insert", D1, "uu-1/pasal-1a", "uu-2/pasal-9/angka-2", "sisipan", label="Pasal 1A"),
        ev("revoke_instrument", D2, "uu-2", "perppu-3/pasal-10", order=-10),
    ]
    versions, _ = build_versions(events)
    restored = on(versions, "uu-1/pasal-1", D2)
    assert (restored.text, restored.source_id) == ("asli", "uu-1/pasal-1")
    assert on(versions, "uu-1/pasal-1a", D2) is None  # inserted by the revoked law: gone


def test_same_day_restatement_leaves_no_zero_length_version():
    events = [
        BASE,
        ev("amend", D1, "uu-1/pasal-1", "uu-2/pasal-9/angka-1", "versi uu-2"),
        ev("revoke_instrument", D2, "uu-2", "perppu-3/pasal-10", order=-10),
        ev("amend", D2, "uu-1/pasal-1", "perppu-3/pasal-9/angka-1", "versi perppu"),
    ]
    versions, _ = build_versions(events)
    mine = [v for v in versions if v.provision_id == "uu-1/pasal-1"]
    assert [v.source_id for v in mine] == [
        "uu-1/pasal-1",
        "uu-2/pasal-9/angka-1",
        "perppu-3/pasal-9/angka-1",
    ]


def test_ruling_makes_the_article_conditional_without_changing_its_text():
    versions, _ = build_versions(
        [BASE, ev("interpret", D3, "uu-1/pasal-1", "mk-5/amar-2", note="sepanjang tidak dimaknai")]
    )
    ruled = on(versions, "uu-1/pasal-1", D3)
    assert ruled.status == "conditional" and ruled.text == "asli"
    assert ruled.rulings == ["mk-5/amar-2"]
    assert ruled.notes == ["[mk-5/amar-2] sepanjang tidak dimaknai"]


def test_instrument_wide_condition_applies_only_to_its_own_wording():
    events = [
        BASE,
        ev("enact", D0, "uu-1/pasal-2", "uu-1/pasal-2", "tetap", label="Pasal 2"),
        ev("amend", D1, "uu-1/pasal-1", "uu-2/pasal-9/angka-1", "versi uu-2"),
        ev("conditional_instrument", D2, "uu-2", "mk-7"),
    ]
    versions, _ = build_versions(events)
    assert on(versions, "uu-1/pasal-1", D2).status == "conditional"
    assert on(versions, "uu-1/pasal-2", D2).status == "in_force"


def test_warns_about_changes_to_articles_that_do_not_exist():
    _, warnings = build_versions([ev("delete", D1, "uu-1/pasal-9", "uu-2/pasal-9/angka-3")])
    assert warnings and "does not exist" in warnings[0]


# ---------------------------------------------------------------- properties

DAYS = [D0 + timedelta(days=365 * n) for n in range(8)]
PROVISIONS = ["uu-1/pasal-1", "uu-1/pasal-2", "uu-1/pasal-3"]

change = st.builds(
    lambda op, day, target, n: ev(op, day, target, f"uu-9/pasal-1/angka-{n}", f"teks {n}"),
    st.sampled_from(["amend", "insert", "delete", "interpret"]),
    st.sampled_from(DAYS),
    st.sampled_from(PROVISIONS),
    st.integers(min_value=0, max_value=10**6),
)


def state(versions: list[Version], day: date) -> dict:
    return {
        pid: (v.text, v.status, v.source_id)
        for pid in PROVISIONS
        if (v := on(versions, pid, day)) is not None
    }


@settings(max_examples=300, deadline=None)
@given(st.lists(change, max_size=12, unique_by=lambda e: e.id))
def test_versions_of_an_article_never_overlap_and_leave_no_gaps(changes):
    enacted = [ev("enact", D0, pid, pid, "asli") for pid in PROVISIONS]
    versions, _ = build_versions(enacted + changes)
    for pid in PROVISIONS:
        mine = sorted((v for v in versions if v.provision_id == pid), key=lambda v: v.valid_from)
        for earlier, later in zip(mine, mine[1:], strict=False):
            assert earlier.valid_to == later.valid_from  # contiguous, no overlap
        assert mine[-1].valid_to is None


@settings(max_examples=300, deadline=None)
@given(st.lists(change, max_size=12, unique_by=lambda e: e.id), change)
def test_a_new_event_never_changes_the_law_before_its_date(changes, extra):
    enacted = [ev("enact", D0, pid, pid, "asli") for pid in PROVISIONS]
    before, _ = build_versions(enacted + changes)
    after, _ = build_versions(enacted + changes + [extra])
    for day in DAYS:
        for probe in (day - timedelta(days=1), day):
            if probe < extra.effective_on:
                assert state(before, probe) == state(after, probe)

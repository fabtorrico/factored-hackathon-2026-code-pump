"""Deterministic demo customer profiles for the Phase 5A prototype.

The curated customer table holds 150,000 rows, of which only a few thousand have any transaction
at all, so opening a session for a customer chosen at random would usually produce an empty
account. This module derives a small fixed set of scenario profiles from the curated transactions
instead, so the customer experience always has real banking activity to demonstrate.

Three properties matter:

- **Deterministic.** Every profile is the top row of a query with a total ordering, so the same
  curated database always yields the same profiles. No randomness, no wall-clock input.
- **Verifiable.** Every statement a profile makes is something the selection query just proved:
  the counts, the status, and any prefill filter are read from the same rows the query ranked. A
  profile never describes a transaction type, amount or date that was not selected on.
- **Non-identifying.** A profile carries a scenario and a display label, never a customer
  identifier and never a curated customer attribute. The customer id stays in-process so the
  frontend can open a session without learning which curated customer it is acting as.

Demo-only support code for the prototype. It is not part of the Banking Core and it grants no
access: a profile only chooses which customer a demo session is opened for, and every subsequent
read still authenticates and authorizes exactly as it did before.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum, unique
from functools import lru_cache
from pathlib import Path

import duckdb

from app.banking.errors import DataUnavailableError


@unique
class DemoScenario(StrEnum):
    """The situation a demo profile exists to demonstrate."""

    DECLINED = "declined"
    PENDING = "pending"
    REVERSED = "reversed"
    AMBIGUOUS = "ambiguous"


# Display labels are fixed text chosen for the prototype. The curated customer table carries no
# name and organizer names are never read, so there is nothing to derive a label from.
DISPLAY_LABELS: dict[DemoScenario, str] = {
    DemoScenario.DECLINED: "Demo Customer A",
    DemoScenario.PENDING: "Demo Customer B",
    DemoScenario.REVERSED: "Demo Customer C",
    DemoScenario.AMBIGUOUS: "Demo Customer D",
}

# Headlines stay type-agnostic on purpose. A curated customer may have a declined withdrawal or a
# pending purchase, and the selection query does not look at the type, so the copy must not claim
# one. Each sentence restates only what the scenario guarantees.
HEADLINES: dict[DemoScenario, str] = {
    DemoScenario.DECLINED: "Has an earlier movement that was declined",
    DemoScenario.PENDING: "Has an earlier movement that is still in progress",
    DemoScenario.REVERSED: "Has an earlier movement that was reversed",
    DemoScenario.AMBIGUOUS: "Has two movements of the same type and currency",
}

_STATUS_SELECTION = """
SELECT customer_id,
       count(*) AS total,
       count(*) FILTER (WHERE transaction_status = ?) AS matches
FROM transactions
GROUP BY customer_id
HAVING matches >= 1
ORDER BY matches DESC, total DESC, customer_id ASC
LIMIT 1
"""

# A customer reference is ambiguous when at least two movements share a type and currency, so
# narrowing a search on those two fields still cannot single one out. That is the situation the
# workflow must clarify rather than guess at, so this profile ranks customers that can produce it.
_AMBIGUOUS_SELECTION = """
WITH groups AS (
    SELECT customer_id,
           transaction_type,
           currency,
           count(*) AS group_size,
           count(*) FILTER (WHERE transaction_status <> 'Approved') AS problems
    FROM transactions
    GROUP BY customer_id, transaction_type, currency
    HAVING count(*) >= 2
)
SELECT g.customer_id,
       max(g.group_size) AS largest_group,
       max(g.problems) AS problems,
       (SELECT count(*) FROM transactions t WHERE t.customer_id = g.customer_id) AS total
FROM groups g
GROUP BY g.customer_id
ORDER BY largest_group DESC, problems DESC, g.customer_id ASC
LIMIT 1
"""

# The repeated pair for the selected customer, taken from the group that made it ambiguous, with a
# total ordering so the profile's prefill filter is stable across runs.
_REPEATED_PAIR_SELECTION = """
SELECT transaction_type, currency
FROM transactions
WHERE customer_id = ?
GROUP BY transaction_type, currency
HAVING count(*) >= 2
ORDER BY transaction_type ASC, currency ASC
LIMIT 1
"""


@dataclass(frozen=True, slots=True)
class DemoProfile:
    """One selectable demo profile. Holds no curated customer identifier."""

    profile_id: str
    display_name: str
    scenario: DemoScenario
    headline: str
    transaction_count: int
    highlight_status: str | None
    highlight_count: int
    prefill_filters: Mapping[str, str] | None = field(default=None)


@dataclass(frozen=True, slots=True)
class DemoSelection:
    """A profile together with the curated customer it stands for.

    In-process only. This is the one place a profile id becomes a customer id, and the customer id
    is never part of a serialized profile.
    """

    profile: DemoProfile
    customer_id: str


def _connect(database_path: Path) -> duckdb.DuckDBPyConnection:
    if not database_path.is_file():
        raise DataUnavailableError(f"curated database missing: {database_path}")
    try:
        return duckdb.connect(str(database_path), read_only=True)
    except duckdb.Error as exc:
        raise DataUnavailableError(f"curated database cannot be opened: {exc}") from exc


def _fetchone(
    connection: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> tuple[object, ...] | None:
    try:
        return connection.execute(sql, list(parameters)).fetchone()
    except duckdb.Error as exc:
        raise DataUnavailableError(f"curated demo query failed: {exc}") from exc


def _select_status_profile(
    connection: duckdb.DuckDBPyConnection,
    scenario: DemoScenario,
) -> DemoSelection | None:
    status = scenario.name.capitalize()
    row = _fetchone(connection, _STATUS_SELECTION, (status,))
    if row is None:
        return None
    customer_id, total, matches = row
    return DemoSelection(
        profile=DemoProfile(
            profile_id=scenario.value,
            display_name=DISPLAY_LABELS[scenario],
            scenario=scenario,
            headline=HEADLINES[scenario],
            transaction_count=int(total),
            highlight_status=status,
            highlight_count=int(matches),
        ),
        customer_id=str(customer_id),
    )


def _select_ambiguous_profile(
    connection: duckdb.DuckDBPyConnection,
    scenario: DemoScenario,
) -> DemoSelection | None:
    row = _fetchone(connection, _AMBIGUOUS_SELECTION)
    if row is None:
        return None
    customer_id, _largest_group, problems, total = row
    customer_id = str(customer_id)

    pair = _fetchone(connection, _REPEATED_PAIR_SELECTION, (customer_id,))
    prefill = None
    if pair is not None:
        # Guaranteed by the selection above to match at least two movements, so a frontend search
        # using it provably cannot resolve to a single transaction.
        prefill = {"transaction_type": str(pair[0]), "currency": str(pair[1])}

    return DemoSelection(
        profile=DemoProfile(
            profile_id=scenario.value,
            display_name=DISPLAY_LABELS[scenario],
            scenario=scenario,
            headline=HEADLINES[scenario],
            transaction_count=int(total),
            highlight_status=None,
            highlight_count=int(problems),
            prefill_filters=prefill,
        ),
        customer_id=customer_id,
    )


@lru_cache(maxsize=4)
def discover_demo_profiles(database_path: Path) -> tuple[DemoSelection, ...]:
    """Select one profile per scenario, deterministically, from the curated transactions.

    A scenario with nothing to select is skipped rather than filled with a placeholder, so every
    profile returned describes activity that genuinely exists in the curated data.
    """

    selected: list[DemoSelection] = []
    claimed: set[str] = set()
    connection = _connect(database_path)
    try:
        for scenario in DemoScenario:
            chosen = (
                _select_ambiguous_profile(connection, scenario)
                if scenario is DemoScenario.AMBIGUOUS
                else _select_status_profile(connection, scenario)
            )
            if chosen is None or chosen.customer_id in claimed:
                # Two scenarios pointing at one customer would make the demo labels ambiguous about
                # what is actually on screen, so the later scenario is dropped.
                continue
            claimed.add(chosen.customer_id)
            selected.append(chosen)
    finally:
        connection.close()
    return tuple(selected)


def list_demo_profiles(database_path: Path) -> tuple[DemoProfile, ...]:
    """The public view of the catalogue: profiles without any curated customer identifier."""

    return tuple(selected.profile for selected in discover_demo_profiles(database_path))


def resolve_demo_selection(database_path: Path, profile_id: str) -> DemoSelection:
    """The profile and the curated customer behind a profile id, resolved together.

    This is the only place a profile id turns into a customer id. It stays in-process: callers use
    the customer id to open a session and the profile to label it, and never serialize it.

    Raises `LookupError` for an unknown profile; callers translate that into a request error.
    """

    wanted = (profile_id or "").strip()
    for selected in discover_demo_profiles(database_path):
        if selected.profile.profile_id == wanted:
            return selected
    raise LookupError(wanted)

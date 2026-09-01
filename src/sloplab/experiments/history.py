"""Cross-run decision history for benchmark runs.

``repeat_stability`` (sloplab.scoring.comparison) measures agreement *within* one
run's repeats. This module records one decision per case per run so drift caused
by a model swap or a corpus change becomes visible *across* runs.

Placement and boundaries:

- This is run provenance, not scoring. It lives under ``experiments/`` because
  ``docs/reproducibility.md`` guarantees that no wall-clock input participates in
  mutation, evaluation, or scoring - and every entry here is timestamped.
- Nothing under ``src/sloplab/evaluators/`` may import this module: an evaluator
  that could read its own prior decision would be gaming the benchmark
  (docs/evaluator-contract.md, rule 4). A regression test enforces the boundary.
- History is keyed by the TRUE ``case_id`` from ``CaseRecord``, never by the
  opaque handle evaluators see.

Durability: the file is rewritten in full and swapped in with ``os.replace``, so
a reader never observes a partial file. That is not the same as safe concurrency -
two runs writing at once will lose one set of entries (last writer wins). Neither
a corrupt file on read nor a failure on write may ever abort a run; both degrade
to a warning.
"""

from __future__ import annotations

import json
import os
import tempfile
import warnings
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sloplab.models.run import CaseRecord

#: Conventional file name; callers choose the directory.
DEFAULT_HISTORY_FILENAME = "decision-history.json"

#: Bumped only on an incompatible on-disk change.
SCHEMA_VERSION = 1


class IncompatibleHistoryError(Exception):
    """The file was written by a newer build and must not be overwritten.

    Distinct from corruption on purpose. Corrupt content carries no information,
    so starting fresh loses nothing; a forward-version file is somebody's intact
    history, and rewriting it would destroy data this build simply cannot read.
    """


class UnreadableHistoryError(Exception):
    """The file exists but could not be read, so its contents are unknown.

    Also distinct from corruption. A permission error says nothing about whether
    the file is intact - and the directory may still be writable, so proceeding
    would ``os.replace`` an accumulated history that was never even parsed.
    """


_ENTRY_FIELDS = ("ts", "decision", "model", "corpus_version", "run_id")


def utc_timestamp() -> str:
    """Second-resolution UTC stamp; the only wall-clock read in this module."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _warn(message: str) -> None:
    warnings.warn(f"decision history: {message}", UserWarning, stacklevel=3)


@dataclass(frozen=True, order=True)
class HistoryEntry:
    """One case's decision in one run.

    Field order is also the sort order, so entries sharing a timestamp still
    order deterministically (``run_id`` breaks the tie, then the rest).
    """

    ts: str
    run_id: str
    model: str
    corpus_version: str
    decision: str

    def as_dict(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in _ENTRY_FIELDS}

    @classmethod
    def from_dict(cls, raw: Any) -> HistoryEntry:
        """Parse one stored entry, raising ``ValueError`` on any deviation."""
        if not isinstance(raw, dict):
            raise ValueError(f"entry must be an object, got {type(raw).__name__}")
        missing = [field for field in _ENTRY_FIELDS if field not in raw]
        if missing:
            raise ValueError(f"entry is missing {', '.join(missing)}")
        values = {field: raw[field] for field in _ENTRY_FIELDS}
        for field, value in values.items():
            if not isinstance(value, str):
                raise ValueError(f"entry field '{field}' must be a string")
        return cls(**values)


class DecisionHistory:
    """Append-only-by-intent history keyed by true case id.

    The whole structure is held in memory and rewritten on save; ``append`` keeps
    each case's entries sorted so ordering never depends on insertion order.
    """

    def __init__(self, cases: Mapping[str, Iterable[HistoryEntry]] | None = None) -> None:
        self._cases: dict[str, list[HistoryEntry]] = {}
        for case_id, entries in (cases or {}).items():
            self._cases[case_id] = sorted(entries)

    # -- reading -----------------------------------------------------------

    def case_ids(self) -> list[str]:
        return sorted(self._cases)

    def entries(self, case_id: str) -> list[HistoryEntry]:
        return list(self._cases.get(case_id, ()))

    def stable_cases(
        self,
        threshold: int = 3,
        *,
        model: str | None = None,
        corpus_version: str | None = None,
    ) -> set[str]:
        """Case ids whose last ``threshold`` entries all share one decision.

        A case with fewer than ``threshold`` matching entries is never stable.

        ``model`` and ``corpus_version`` are not conveniences. One history file
        may hold entries from several evaluators or several corpus revisions, and
        comparing decisions across that boundary answers no useful question -
        filter to a single producer before reading stability off this.
        """
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")

        stable: set[str] = set()
        for case_id, entries in self._cases.items():
            selected = [
                entry
                for entry in entries
                if (model is None or entry.model == model)
                and (corpus_version is None or entry.corpus_version == corpus_version)
            ]
            window = selected[-threshold:]
            if len(window) < threshold:
                continue
            if len({entry.decision for entry in window}) == 1:
                stable.add(case_id)
        return stable

    # -- writing -----------------------------------------------------------

    def append(self, case_id: str, entry: HistoryEntry) -> None:
        entries = self._cases.setdefault(case_id, [])
        entries.append(entry)
        entries.sort()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "cases": {
                case_id: [entry.as_dict() for entry in self._cases[case_id]]
                for case_id in sorted(self._cases)
            },
        }

    def save(self, path: Path) -> None:
        """Write the whole file, then swap it in atomically.

        The temp file is created in the destination directory so ``os.replace``
        stays within one filesystem, and is removed if anything fails.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.as_dict(), indent=2, sort_keys=False) + "\n"

        handle, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> DecisionHistory:
        """Load a history file. A missing file is empty; a broken one warns.

        It raises only when the existing file must be preserved:
        :class:`IncompatibleHistoryError` for a newer schema, and
        :class:`UnreadableHistoryError` when the bytes could not be read at all.
        Malformed or wrong-shaped content yields a fresh history, because that
        content carries nothing worth keeping.
        """
        try:
            raw_text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls()
        except OSError as exc:
            raise UnreadableHistoryError(f"cannot read {path} ({exc})") from exc

        try:
            return cls(_parse_payload(json.loads(raw_text)))
        except IncompatibleHistoryError:
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            _warn(f"{path} is unusable ({exc}); starting fresh")
            return cls()


def _parse_payload(payload: Any) -> dict[str, list[HistoryEntry]]:
    if not isinstance(payload, dict):
        raise ValueError(f"top level must be an object, got {type(payload).__name__}")
    version = payload.get("schema_version")
    if isinstance(version, int) and version > SCHEMA_VERSION:
        raise IncompatibleHistoryError(
            f"file uses schema_version {version}, this build understands "
            f"{SCHEMA_VERSION}; refusing to overwrite it"
        )
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {version!r}")
    cases = payload.get("cases")
    if not isinstance(cases, dict):
        raise ValueError("'cases' must be an object")

    parsed: dict[str, list[HistoryEntry]] = {}
    for case_id, entries in cases.items():
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case ids must be non-empty strings")
        if not isinstance(entries, list):
            raise ValueError(f"entries for '{case_id}' must be a list")
        parsed[case_id] = [HistoryEntry.from_dict(entry) for entry in entries]
    return parsed


def entries_from_records(
    records: Iterable[CaseRecord],
    *,
    model: str,
    corpus_version: str,
    run_id: str,
    ts: str | None = None,
) -> dict[str, HistoryEntry]:
    """Collapse one run's records into one entry per case.

    A pilot run produces ``repeats`` records per case; writing all of them would
    let ``stable_cases(threshold=3)`` be satisfied inside a single run, which is
    ``repeat_stability`` under another name. So repeats are reduced to their
    majority decision here.

    Failed evaluations are dropped, matching the runbook's rule that they are
    excluded from accuracy-style statements; a case whose every record failed
    contributes nothing. Majority ties are broken by sorted decision value so the
    result never depends on record order.
    """
    stamp = ts if ts is not None else utc_timestamp()
    votes: dict[str, Counter[str]] = {}
    for record in records:
        if record.evaluation_metadata.get("failed"):
            continue
        votes.setdefault(record.case_id, Counter())[str(record.decision)] += 1

    entries: dict[str, HistoryEntry] = {}
    for case_id, counter in votes.items():
        if not counter:
            continue
        decision = min(counter.items(), key=lambda item: (-item[1], item[0]))[0]
        entries[case_id] = HistoryEntry(
            ts=stamp,
            run_id=run_id,
            model=model,
            corpus_version=corpus_version,
            decision=decision,
        )
    return entries


def record_run(path: Path, entries: Mapping[str, HistoryEntry]) -> bool:
    """Merge one run's entries into the history file. Returns success.

    This is the only function callers need. It never raises: the pilot is the one
    path that spends money, and an exception here - after results are already on
    disk - would turn a completed run into a failed one.
    """
    return record_runs(path, [entries])


def record_runs(path: Path, entry_sets: Iterable[Mapping[str, HistoryEntry]]) -> bool:
    """Merge several runs' entries into the history file in one load/save cycle.

    A benchmark run evaluates several evaluators over the same cases. Calling
    :func:`record_run` per evaluator would re-read, re-serialize, fsync and
    atomically replace the whole file once per evaluator; this does it once.
    """
    batches = [entries for entries in entry_sets if entries]
    if not batches:
        return False
    try:
        history = DecisionHistory.load(path)
    except (IncompatibleHistoryError, UnreadableHistoryError) as exc:
        # Refusing to write is the point: the file on disk may be intact and
        # simply unread, and overwriting it would destroy accumulated history.
        _warn(f"{exc}; refusing to overwrite it, run results are unaffected")
        return False
    except Exception as exc:  # noqa: BLE001 - history must never fail a run
        _warn(f"could not read {path} ({exc}); run results are unaffected")
        return False

    try:
        for entries in batches:
            for case_id, entry in sorted(entries.items()):
                history.append(case_id, entry)
        history.save(path)
        return True
    except Exception as exc:  # noqa: BLE001 - history must never fail a run
        _warn(f"could not update {path} ({exc}); run results are unaffected")
        return False

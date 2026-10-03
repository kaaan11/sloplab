"""Descriptive decision/confidence variability from verified LLM pilot bundles."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sloplab.experiments.bundle import BundleError, verify_bundle
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import _pair_ids_from_root


class VarianceError(ValueError):
    """Observations cannot be combined without changing their meaning."""


def _interval(
    values: dict[str, list[int]], samples: int, confidence: float, seed: int
) -> list[float] | None:
    if not values:
        return None
    groups = sorted(values)
    if len(groups) < 2:
        return None
    rng = random.Random(seed)
    distribution = []
    for _ in range(samples):
        draw = [v for group in rng.choices(groups, k=len(groups)) for v in values[group]]
        distribution.append(sum(draw) / len(draw))
    distribution.sort()
    tail = (1 - confidence) / 2
    return [distribution[int(tail * (samples - 1))], distribution[int((1 - tail) * (samples - 1))]]


def analyze_variance(
    paths: list[Path],
    *,
    samples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
    corpus_root: Path | None = None,
) -> dict[str, Any]:
    """Keep source observations distinct; failures never become decisions.

    Conditions with different model/prompt/output settings are kept separate.
    Within a condition, a case must have one rendered input hash. A case's flip
    rate contributes to the interval only if every planned observation succeeded
    and at least two are available. Bootstrap units are logical report clusters.
    """
    if samples < 100 or not 0 < confidence < 1 or not paths:
        raise VarianceError("provide bundles, >=100 bootstrap samples, and confidence in (0,1)")
    pair_ids = _pair_ids_from_root(corpus_root)
    groups: dict[str, dict[str, Any]] = {}
    fingerprints: set[str] = set()
    for path in paths:
        try:
            completion = verify_bundle(path, kind="llm-pilot")
        except BundleError as exc:
            raise VarianceError(str(exc)) from exc
        fingerprint = hashlib.sha256(json.dumps(completion, sort_keys=True).encode()).hexdigest()
        if fingerprint in fingerprints:
            raise VarianceError("same observation bundle supplied more than once")
        fingerprints.add(fingerprint)
        manifest = json.loads((path / "manifest.json").read_text())
        settings = {
            key: manifest.get(key)
            for key in (
                "model_id",
                "prompt_hash",
                "prompt_renderer_version",
                "output_mode",
                "response_schema_sha256",
                "provider_require_parameters",
                "temperature",
            )
        }
        if not settings["model_id"] or not settings["prompt_hash"]:
            raise VarianceError("pilot manifest lacks model/prompt identity")
        condition = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
        group = groups.setdefault(condition, {"settings": settings, "sources": [], "cases": {}})
        group["sources"].append({"bundle_sha256": fingerprint, "base_seed": manifest["base_seed"]})
        records = {}
        for line in (path / "records.jsonl").read_text().splitlines():
            record = CaseRecord.model_validate_json(line)
            repeat = record.evaluation_metadata.get("repeat_index")
            if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 0:
                raise VarianceError("record lacks a valid repeat index")
            key = record.case_id, repeat
            if key in records:
                raise VarianceError("duplicate observation inside bundle")
            if record.evaluation_metadata.get("failed"):
                raise VarianceError("failed evaluation encoded as a decision record")
            if not math.isfinite(record.confidence) or not 0 <= record.confidence <= 1:
                raise VarianceError("invalid confidence observation")
            records[key] = record
        seen = set()
        for line in (path / "outcomes.jsonl").read_text().splitlines():
            outcome = json.loads(line)
            repeat = outcome["repeat_index"]
            if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 0:
                raise VarianceError("outcome lacks a valid repeat index")
            key = outcome["case_id"], outcome["repeat_index"]
            if key in seen or outcome["status"] not in {"success", "failed", "not_run"}:
                raise VarianceError("duplicate or unknown outcome")
            seen.add(key)
            observed = records.get(key)
            if (outcome["status"] == "success") != (observed is not None):
                raise VarianceError("outcome and decision records disagree")
            case = group["cases"].setdefault(
                key[0], {"statuses": Counter(), "records": [], "hashes": set(), "cluster": key[0]}
            )
            case["statuses"][outcome["status"]] += 1
            if observed is not None:
                rendered = observed.evaluation_metadata.get("rendered_prompt_hash")
                if not isinstance(rendered, str) or not re.fullmatch(r"[0-9a-f]{64}", rendered):
                    raise VarianceError("record lacks rendered input identity")
                case["hashes"].add(rendered)
                if len(case["hashes"]) > 1:
                    raise VarianceError("same case ID has different rendered inputs")
                parent = observed.parent_id or observed.case_id
                cluster = pair_ids.get(parent, parent)
                if case["records"] and case["cluster"] != cluster:
                    raise VarianceError("case parent identity changed across observations")
                case["cluster"] = cluster
                case["records"].append(observed)
        if set(records) - seen:
            raise VarianceError("decision without an outcome")
        if manifest.get("planned", len(seen)) != len(seen):
            raise VarianceError("outcome count differs from planned observations")
    output = []
    for condition, group in sorted(groups.items()):
        cases = []
        clusters: dict[str, list[int]] = defaultdict(list)
        totals: Counter[str] = Counter()
        for case_id, case in sorted(group["cases"].items()):
            statuses = case["statuses"]
            totals.update(statuses)
            records = case["records"]
            decisions = Counter(r.decision.value for r in records)
            confs = [r.confidence for r in records]
            complete = statuses["success"] == sum(statuses.values())
            eligible = complete and len(records) >= 2
            observed_flip = len(decisions) > 1
            if eligible:
                clusters[case["cluster"]].append(int(observed_flip))
            cases.append(
                {
                    "case_id": case_id,
                    "cluster_id": case["cluster"],
                    "planned_observations": sum(statuses.values()),
                    "statuses": dict(statuses),
                    "complete": complete,
                    "eligible_for_flip_interval": eligible,
                    "decision_counts": dict(sorted(decisions.items())),
                    "observed_decision_flip": observed_flip if records else None,
                    "confidence_mean": statistics.mean(confs) if confs else None,
                    "confidence_population_sd": statistics.pstdev(confs) if confs else None,
                    "confidence_range": max(confs) - min(confs) if confs else None,
                }
            )
        eligible_values = [v for vs in clusters.values() for v in vs]
        output.append(
            {
                "condition_id": condition,
                **group["settings"],
                "sources": group["sources"],
                "cases": cases,
                "observation_statuses": dict(totals),
                "eligible_cases": len(eligible_values),
                "logical_report_clusters": len(clusters),
                "flip_rate": sum(eligible_values) / len(eligible_values)
                if eligible_values
                else None,
                "flip_rate_interval": _interval(clusters, samples, confidence, seed),
            }
        )
    return {
        "schema_version": "llm-variance-v1",
        "bootstrap_samples": samples,
        "confidence_level": confidence,
        "bootstrap_seed": seed,
        "unit": "logical report cluster; complete cases with >=2 valid observations",
        "cluster_source": (
            "corpus pair_id plus parent_id"
            if corpus_root is not None
            else "parent_id or case_id; presentation pair mapping unavailable"
        ),
        "seed_note": (
            "base_seed records run provenance; it does not establish provider decoding seed control"
        ),
        "interpretation": "descriptive variability on supplied inputs; no general accuracy claim",
        "conditions": output,
    }

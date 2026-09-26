"""Deterministic, dependency-free, offline HTML over existing scoring APIs.

No scripts, remote resources, wall clock, report text, raw exceptions or absolute
input paths. Only escaped text and bounded numeric SVG geometry enter the page.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from sloplab.experiments.bundle import open_result_dir
from sloplab.models.run import CaseRecord, RunMetadata
from sloplab.reporting.outcomes import FailureLedger, read_failure_outcomes
from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.comparison import bootstrap_accuracy_ci, per_operator_metrics
from sloplab.scoring.metrics import MetricBundle, compute_metrics

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_CI = 0.95

# Styles are constant, never assembled from evaluator/metadata strings.
_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f5f7fa; --panel: #ffffff; --ink: #172b41; --muted: #495d72;
  --line: #cbd5e1; --accent: #174cb0; --track: #dbe4f2;
  --notice: #fff5dc; --notice-ink: #654600; --focus: #a03f00;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1520; --panel: #142131; --ink: #e8eef7; --muted: #b0c0d3;
    --line: #40536a; --accent: #8cb7ff; --track: #33465e;
    --notice: #302918; --notice-ink: #ffe0a0; --focus: #ffcf8a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { width: min(1160px, calc(100% - 40px)); margin: 48px auto; }
a { color: var(--accent); text-underline-offset: 3px; }
a:focus-visible, [tabindex]:focus-visible { outline: 3px solid var(--focus);
  outline-offset: 4px;
  }
.eyebrow { font-size: .78rem;
  letter-spacing: .16em;
  font-weight: 750;
  text-transform: uppercase;
  }
h1 { font-size: clamp(2rem, 5vw, 3.2rem);
  line-height: 1.15;
  margin: 12px 0;
  letter-spacing: -.035em;
  }
h2 { font-size: 1.45rem; margin: 0 0 8px; letter-spacing: -.02em; }
h3 { font-size: 1rem; margin: 18px 0 6px; }
p { margin: 8px 0 16px; }
.subtle { color: var(--muted); }
nav { display: flex; flex-wrap: wrap; gap: 10px 24px; margin: 26px 0; }
section { padding: 28px;
  margin: 24px 0;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  }
.notice { background: var(--notice);
  color: var(--notice-ink);
  border-left: 5px solid var(--notice-ink);
  }
.notice p:last-child { margin-bottom: 0; }
.stats { display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 28px 0;
  }
.stat { padding: 16px 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  }
.stat strong { font-size: 1.85rem; display: block; font-variant-numeric: tabular-nums; }
.stat span { color: var(--muted); font-size: .85rem; }
.table-scroll { max-width: 100%; overflow-x: auto; margin: 20px 0 6px; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
caption { text-align: left; color: var(--muted); margin-bottom: 10px; }
th, td { padding: 13px 14px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--line);
  }
th { font-weight: 700; }
thead th { white-space: normal; }
tbody th { min-width: 175px; overflow-wrap: anywhere; }
.num { white-space: nowrap; font-variant-numeric: tabular-nums; }
small { display: block; font-size: .8rem; color: var(--muted); }
.metric { min-width: 140px; }
svg { display: block; margin-top: 7px; width: 144px; height: 8px; }
.track { fill: var(--track); } .bar { fill: var(--accent); }
code { font-size: .88em; overflow-wrap: anywhere; }
dl { display: grid;
  grid-template-columns: minmax(130px, 190px) minmax(0, 1fr);
  gap: 12px 20px;
  }
dt { color: var(--muted); } dd { margin: 0; overflow-wrap: anywhere; }
footer { color: var(--muted); font-size: .86rem; padding: 12px 0 30px; }
@media (max-width: 640px) {
  main { width: calc(100% - 24px); margin-top: 24px; }
  section { padding: 18px; } .stats { grid-template-columns: 1fr; gap: 8px; }
  .stat strong { font-size: 1.4rem; } dl { grid-template-columns: 1fr; gap: 4px; }
  dd { margin-bottom: 12px; }
}
@media print { body { background: white; color: black; } section { break-inside: avoid; } }
"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: float | None) -> str:
    return f"{value:.3f}" if value is not None and math.isfinite(value) else "Not available"


def _rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None and math.isfinite(value) else "Not available"


def _bar(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    width = 144 * min(1.0, max(0.0, value))
    return (
        '<svg viewBox="0 0 144 8" aria-hidden="true" focusable="false">'
        '<rect class="track" width="144" height="8" rx="4"/>'
        f'<rect class="bar" width="{width:.3f}" height="8" rx="4"/></svg>'
    )


def _table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    """Cells are trusted markup constructed here from escaped source strings."""
    heading = "".join(f'<th scope="col">{_text(header)}</th>' for header in headers)
    body = "\n".join(
        "<tr>"
        + f'<th scope="row">{row[0]}</th>'
        + "".join(f"<td>{cell}</td>" for cell in row[1:])
        + "</tr>"
        for row in rows
    )
    return (
        '<div class="table-scroll" role="region" tabindex="0" '
        f'aria-label="{_text(caption)}"><table><caption>{_text(caption)}</caption>'
        f"<thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _versions(metadata: RunMetadata | None, records: list[CaseRecord]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for info in metadata.evaluators if metadata else []:
        name, version = info.name, info.version
        if name in versions and versions[name] != version:
            raise ValueError("Evaluator has multiple versions; compare separate runs instead.")
        versions[name] = version
    for record in records:
        name, version = record.evaluator_name, record.evaluator_version
        if name in versions and versions[name] != version:
            raise ValueError("Evaluator version differs across metadata/records; cannot pool.")
        versions[name] = version
    return versions


def render_html(
    metadata: RunMetadata | None, records: list[CaseRecord], ledger: FailureLedger
) -> str:
    """Render identical input artifacts to identical UTF-8 HTML, independent of cwd."""
    versions = _versions(metadata, records)
    for failure in ledger.failures:
        versions.setdefault(failure.evaluator_name, "Not recorded")
    names = sorted(versions)
    grouped: dict[str, list[CaseRecord]] = defaultdict(list)
    for record in records:
        grouped[record.evaluator_name].append(record)
    for group in grouped.values():
        group.sort(key=lambda record: record.case_id)
    bundles = {name: compute_metrics(grouped[name], name) for name in names}
    seed = metadata.base_seed if metadata else 0
    suite = metadata.suite_name if metadata else "Not recorded"
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
        f"<title>SlopLab results · {_text(suite)}</title><style>{_STYLE}</style></head><body>",
        '<main><header><div class="eyebrow">SlopLab / Offline evaluation report</div>',
        "<h1>Evaluator comparison</h1>",
        f'<p class="subtle">Suite: <strong>{_text(suite)}</strong> · Synthetic report corpus</p>',
        '<nav aria-label="Report sections"><a href="#interpretation">Read this first</a>'
        '<a href="#summary">Evaluators</a><a href="#operators">Operators</a>'
        '<a href="#failures">Execution failures</a><a href="#metadata">Run metadata</a></nav>',
        '</header><section id="interpretation" class="notice"><h2>What these numbers are</h2>',
        "<p><strong>Authored target agreement, not verified real-world triage accuracy "
        "or bug-bounty performance.</strong> These measurements compare evaluator decisions "
        "with human-authored targets on a synthetic corpus under controlled text mutations.</p>",
        "<p>Canonical reports and their variants are correlated, not independent real-world "
        "reports. Good agreement does not establish general security-review competence.</p>",
        "<p><strong>Rules-baseline surface-signature risk:</strong> its regex rules overlap "
        "with fixed mutation-template wording. Detection can reflect recognition of those "
        "phrases rather than semantic understanding. The pre-registered ablation was "
        "inconclusive; the larger post-hoc ablation is exploratory.</p></section>",
    ]
    if "oracle" in names:
        parts.append(
            '<p class="notice">Oracle is a label-reading plumbing control, '
            "not a content-based evaluator or a competitor.</p>"
        )
    scored = sum(bundle.total_cases for bundle in bundles.values())
    failures_label = str(len(ledger.failures)) if ledger.available else "Unknown"
    parts.append(
        '<div class="stats">'
        f'<div class="stat"><strong>{len(names)}</strong><span>Evaluators in this run</span></div>'
        f'<div class="stat"><strong>{scored}</strong><span>Scored case evaluations</span></div>'
        f'<div class="stat"><strong>{failures_label}</strong>'
        "<span>Operational failures — not scored</span></div></div>"
    )
    parts.extend(
        [
            '<section id="summary"><h2>Evaluator summary</h2>',
            '<p class="subtle">Accuracy and mutation detection: higher is better. '
            "False reassurance, over-rejection and ECE: lower is better. "
            "Not available means no eligible observations, not zero error.</p>",
        ]
    )
    rows: list[list[str]] = []
    for name in names:
        bundle = bundles[name]
        eligible = [r for r in grouped[name] if r.expected_decision is not None]
        if eligible:
            low, _, high = bootstrap_accuracy_ci(
                eligible, resamples=BOOTSTRAP_RESAMPLES, ci=BOOTSTRAP_CI, seed=seed
            )
            interval = f"{_rate(low)} – {_rate(high)}"
        else:
            interval = "Not available"
        accuracy = bundle.decision_accuracy if bundle.total_cases else None
        rows.append(
            [
                f"{_text(name)}<small>Version {_text(versions[name])}</small>",
                f'<span class="num">{bundle.total_cases}</span>',
                f'<span class="num">{_rate(accuracy)}</span>{_bar(accuracy)}',
                f'<span class="num">{interval}</span>',
                _rate(bundle.mutation_detection_rate),
                _rate(bundle.false_reassurance_rate),
                _rate(bundle.over_rejection_rate),
                _number(bundle.calibration_error),
            ]
        )
    parts.append(
        _table(
            "Agreement with authored targets, using only scored CaseRecord observations",
            [
                "Evaluator",
                "Cases scored",
                "Decision accuracy",
                "95% bootstrap CI",
                "Mutation detection",
                "False reassurance",
                "Over-rejection",
                "ECE",
            ],
            rows,
        )
    )
    parts.append(
        f'<p class="subtle">Case-level percentile bootstrap: {BOOTSTRAP_RESAMPLES:,} resamples, '
        f"95% interval, explicit seed {_text(seed)}. This existing helper does not cluster by "
        "canonical parent; do not interpret its interval as real-world uncertainty.</p></section>"
    )
    parts.append('<section id="operators"><h2>Operator breakdown</h2>')
    parts.append(
        '<p class="subtle">Mutated cases only. Each cell shows scored cases and decision '
        "accuracy for that operator. Compare coverage before comparing percentages.</p>"
    )
    operator_groups = {name: per_operator_metrics(grouped[name]) for name in names}
    operators = sorted({op for groups in operator_groups.values() for op in groups})
    if operators:
        operator_rows: list[list[str]] = []
        for operator in operators:
            cells = [_text(operator)]
            for name in names:
                op_bundle: MetricBundle | None = operator_groups[name].get(operator)
                if op_bundle is None or not op_bundle.total_cases:
                    cells.append("0 cases<small>Not available</small>")
                else:
                    cells.append(
                        f'<div class="metric">{op_bundle.total_cases} cases · '
                        f"{_rate(op_bundle.decision_accuracy)}{_bar(op_bundle.decision_accuracy)}</div>"
                    )
            operator_rows.append(cells)
        parts.append(_table("Per-operator decision accuracy", ["Operator", *names], operator_rows))
    else:
        parts.append("<p>No scored operator observations are available.</p>")
    parts.append('</section><section id="failures"><h2>Evaluation failures</h2>')
    parts.append(
        "<p>Operational failures are not incorrect triage decisions. They are not added "
        "to accuracy denominators. Successful records remain the scoring source of truth.</p>"
    )
    if not ledger.available:
        parts.append(
            '<p class="notice">Operational failure ledger not available for this legacy run. '
            "Failure counts cannot be inferred from run.jsonl.</p>"
        )
    else:
        binding = "SHA-256 bound to run metadata" if ledger.bound else "legacy, unbound sidecar"
        parts.append(
            f"<p><strong>{len(ledger.failures)} operational failures.</strong> "
            f"{_text(binding)}.</p>"
        )
        counts = Counter((f.evaluator_name, f.error_kind) for f in ledger.failures)
        totals = Counter(f.evaluator_name for f in ledger.failures)
        parts.append(
            _table(
                "Failures by evaluator",
                ["Evaluator", "Failed evaluations"],
                [[_text(name), str(totals[name])] for name in names],
            )
        )
        if counts:
            parts.append(
                _table(
                    "Recorded error-kind distribution",
                    ["Evaluator", "Error kind", "Count"],
                    [
                        [_text(name), _text(kind), str(count)]
                        for (name, kind), count in sorted(counts.items())
                    ],
                )
            )
    parts.append('</section><section id="metadata"><h2>Run metadata</h2>')
    fields: list[tuple[str, object]] = [
        ("SlopLab version", metadata.sloplab_version if metadata else "Not recorded"),
        ("Suite name", suite),
        ("Suite hash", metadata.suite_hash if metadata else "Not recorded"),
        ("Git commit", metadata.git_commit if metadata and metadata.git_commit else "Not recorded"),
        ("Base seed", metadata.base_seed if metadata else "Not recorded (bootstrap uses 0)"),
        (
            "Recorded timestamp",
            metadata.started_at.isoformat()
            if metadata and "started_at" in metadata.model_fields_set
            else "Not recorded",
        ),
    ]
    parts.append(
        "<dl>"
        + "".join(f"<dt>{_text(key)}</dt><dd>{_text(value)}</dd>" for key, value in fields)
        + "</dl></section>"
    )
    parts.append(
        "<footer>Self-contained HTML · No JavaScript or external resource dependencies. "
        '<a href="https://github.com/kaaan11/sloplab/blob/main/docs/methodology.md">Methodology</a>'
        ' · <a href="https://github.com/kaaan11/sloplab/blob/main/docs/threat-model.md">Limitations</a>'
        "</footer></main></body></html>\n"
    )
    return "\n".join(parts)


def write_html_report(run_path: Path, out_path: Path) -> Path:
    """Consume verified artifacts; fail before writing if provenance is inconsistent."""
    mode = open_result_dir(run_path, purpose="HTML report")
    if mode == "complete" and out_path.resolve().is_relative_to(run_path.parent.resolve()):
        raise ValueError(
            "Write HTML outside the integrity-marked bundle to preserve its completion hashes."
        )
    metadata, records = read_run_jsonl(run_path)
    ledger = read_failure_outcomes(run_path, metadata, records)
    if not records and not (metadata and metadata.evaluators) and not ledger.failures:
        raise ValueError("No evaluator observations or run metadata found for HTML reporting.")
    if out_path.resolve() in {run_path.resolve(), (run_path.parent / "outcomes.jsonl").resolve()}:
        raise ValueError("HTML output must not overwrite run.jsonl or its outcome provenance.")
    content = render_html(metadata, records, ledger)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content.encode("utf-8"))
    return out_path

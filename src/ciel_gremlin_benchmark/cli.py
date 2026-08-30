from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .dataset import dataset_sha256, family_counts, load_tasks
from .experiment import compare_runs
from .manifest import audit_comparability, load_manifest
from .runner import BenchmarkRunner, ReplayAdapter
from .sanity import run_metric_sanity


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _cmd_validate(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    _print_json({
        "status": "PASS",
        "tasks": len(tasks),
        "family_counts": family_counts(tasks),
        "dataset_sha256": dataset_sha256(args.dataset),
    })
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    adapter = ReplayAdapter.from_jsonl(args.predictions, args.system_id)
    records, metrics = BenchmarkRunner(
        enforce_system_contract=args.strict_system_contract
    ).run(tasks, adapter)

    output = {
        "schema": "CIEL_GREMLIN_BENCHMARK_RESULT_V0_1",
        "system_id": args.system_id,
        "dataset_sha256": dataset_sha256(args.dataset),
        "metrics": asdict(metrics),
        "records": records if args.include_records else [],
    }

    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def _cmd_audit_manifests(args: argparse.Namespace) -> int:
    manifests = [load_manifest(path) for path in args.manifests]
    issues = audit_comparability(manifests)
    _print_json({
        "status": "FAIL" if issues else "PASS",
        "systems": [manifest.system_id for manifest in manifests],
        "issues": issues,
        "manifest_commitments": {
            manifest.system_id: manifest.commitment() for manifest in manifests
        },
    })
    return 1 if issues else 0


def _cmd_compare(args: argparse.Namespace) -> int:
    comparison = compare_runs(args.run_dirs)
    output = comparison.to_dict()
    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def _cmd_sanity(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    metrics = run_metric_sanity(tasks)
    _print_json({
        "schema": "CIEL_GREMLIN_METRIC_SANITY_V0_1",
        "status": "PASS",
        "dataset_sha256": dataset_sha256(args.dataset),
        "systems": {system_id: asdict(value) for system_id, value in metrics.items()},
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ciel-gremlin-benchmark")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate and fingerprint a JSONL benchmark dataset")
    validate.add_argument("dataset")
    validate.set_defaults(func=_cmd_validate)

    score = sub.add_parser("score", help="score deterministic replay predictions")
    score.add_argument("dataset")
    score.add_argument("predictions")
    score.add_argument("--system-id", required=True)
    score.add_argument("--output")
    score.add_argument("--include-records", action="store_true")
    score.add_argument(
        "--strict-system-contract",
        action="store_true",
        help="require B1-B4 provenance receipts declared by the adapter contract",
    )
    score.set_defaults(func=_cmd_score)

    audit = sub.add_parser(
        "audit-manifests",
        help="fail closed unless run manifests are directly comparable",
    )
    audit.add_argument("manifests", nargs="+")
    audit.set_defaults(func=_cmd_audit_manifests)

    compare = sub.add_parser(
        "compare",
        help="compare scored run directories after manifest comparability audit",
    )
    compare.add_argument("run_dirs", nargs="+")
    compare.add_argument("--output")
    compare.set_defaults(func=_cmd_compare)

    sanity = sub.add_parser(
        "sanity",
        help="run deterministic metric discrimination sanity controls",
    )
    sanity.add_argument("dataset")
    sanity.set_defaults(func=_cmd_sanity)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .dataset import family_counts, load_tasks
from .runner import BenchmarkRunner, ReplayAdapter


def _cmd_validate(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    print(json.dumps(
        {
            "status": "PASS",
            "tasks": len(tasks),
            "family_counts": family_counts(tasks),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    adapter = ReplayAdapter.from_jsonl(args.predictions, args.system_id)
    records, metrics = BenchmarkRunner().run(tasks, adapter)

    output = {
        "schema": "CIEL_GREMLIN_BENCHMARK_RESULT_V0_1",
        "system_id": args.system_id,
        "metrics": asdict(metrics),
        "records": records if args.include_records else [],
    }

    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ciel-gremlin-benchmark")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a JSONL benchmark dataset")
    validate.add_argument("dataset")
    validate.set_defaults(func=_cmd_validate)

    score = sub.add_parser("score", help="score deterministic replay predictions")
    score.add_argument("dataset")
    score.add_argument("predictions")
    score.add_argument("--system-id", required=True)
    score.add_argument("--output")
    score.add_argument("--include-records", action="store_true")
    score.set_defaults(func=_cmd_score)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

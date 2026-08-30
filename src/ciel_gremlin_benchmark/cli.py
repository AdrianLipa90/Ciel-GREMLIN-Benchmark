from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .dataset import dataset_sha256, family_counts, load_tasks
from .experiment import compare_runs
from .manifest import RunManifest, audit_comparability, file_sha256, load_manifest
from .capture import capture_predictions
from .openai_live import OpenAIResponsesAdapter, ReceiptBundleStore, UrllibOpenAIResponsesTransport
from .preflight import preflight_live
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


def _parse_components(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"component must use name=sha form: {value!r}")
        name, sha = value.split("=", 1)
        name = name.strip()
        sha = sha.strip()
        if not name or not sha:
            raise ValueError(f"component must use non-empty name=sha form: {value!r}")
        if name in out:
            raise ValueError(f"duplicate component {name!r}")
        out[name] = sha
    return out


def _cmd_make_manifest(args: argparse.Namespace) -> int:
    try:
        model_parameters = json.loads(args.model_parameters_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid --model-parameters-json: {exc}") from exc
    if not isinstance(model_parameters, dict):
        raise ValueError("--model-parameters-json must decode to a JSON object")

    manifest = RunManifest(
        run_id=args.run_id,
        system_id=args.system_id,
        dataset_sha256=dataset_sha256(args.dataset),
        benchmark_commit=args.benchmark_commit,
        model_provider=args.model_provider,
        model_id=args.model_id,
        model_parameters=model_parameters,
        prompt_sha256=file_sha256(args.prompt),
        component_commits=_parse_components(args.component),
        replicate=args.replicate,
    )
    issues = manifest.validate()
    if issues:
        raise ValueError("invalid generated run manifest: " + "; ".join(issues))

    output = manifest.to_dict()
    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized + "\n", encoding="utf-8")
    _print_json({
        "status": "PASS",
        "output": str(target),
        "system_id": manifest.system_id,
        "dataset_sha256": manifest.dataset_sha256,
        "prompt_sha256": manifest.prompt_sha256,
        "manifest_commitment": manifest.commitment(),
    })
    return 0


def _cmd_capture_openai(args: argparse.Namespace) -> int:
    try:
        model_parameters = json.loads(args.model_parameters_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid --model-parameters-json: {exc}") from exc
    if not isinstance(model_parameters, dict):
        raise ValueError("--model-parameters-json must decode to a JSON object")

    tasks = load_tasks(args.dataset)
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    receipt_store = (
        ReceiptBundleStore.from_jsonl(args.receipt_bundle)
        if args.receipt_bundle
        else None
    )
    transport = UrllibOpenAIResponsesTransport(
        api_key_env=args.api_key_env,
        url=args.responses_url,
        timeout_s=args.timeout_s,
    )
    adapter = OpenAIResponsesAdapter(
        system_id=args.system_id,
        model_id=args.model_id,
        prompt=prompt,
        transport=transport,
        model_parameters=model_parameters,
        receipt_store=receipt_store,
    )
    predictions = capture_predictions(
        tasks,
        adapter,
        args.output,
        strict_system_contract=args.system_id != "B0",
    )
    _print_json({
        "status": "PASS",
        "system_id": args.system_id,
        "model_id": args.model_id,
        "captured": len(predictions),
        "output": str(args.output),
    })
    return 0


def _cmd_preflight_live(args: argparse.Namespace) -> int:
    prompt_paths = {
        "B0": args.prompt_b0,
        "B1": args.prompt_b1_b3,
        "B3": args.prompt_b1_b3,
        "B2": args.prompt_b2_b4,
        "B4": args.prompt_b2_b4,
    }
    receipt_paths = {
        key: value
        for key, value in {
            "B2": args.receipts_b2,
            "B3": args.receipts_b3,
            "B4": args.receipts_b4,
        }.items()
        if value
    }
    report = preflight_live(
        dataset=args.dataset,
        run_root=args.run_root,
        prompt_paths=prompt_paths,
        receipt_paths=receipt_paths,
        api_key_env=args.api_key_env,
        require_api_key=not args.allow_missing_api_key,
    )
    _print_json(report.to_dict())
    return 0 if report.status == "PASS" else 1


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

    validate = sub.add_parser(
        "validate",
        help="validate and fingerprint a JSONL benchmark dataset",
    )
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

    make_manifest = sub.add_parser(
        "make-manifest",
        help="freeze one B0-B4 run manifest from exact dataset/prompt/component bytes",
    )
    make_manifest.add_argument("--run-id", required=True)
    make_manifest.add_argument("--system-id", required=True)
    make_manifest.add_argument("--dataset", required=True)
    make_manifest.add_argument("--benchmark-commit", required=True)
    make_manifest.add_argument("--model-provider", required=True)
    make_manifest.add_argument("--model-id", required=True)
    make_manifest.add_argument(
        "--model-parameters-json",
        default="{}",
        help='JSON object, e.g. \'{"temperature":0,"seed":7}\'',
    )
    make_manifest.add_argument("--prompt", required=True)
    make_manifest.add_argument(
        "--component",
        action="append",
        default=[],
        help="repeatable component pin in name=40hexsha form",
    )
    make_manifest.add_argument("--replicate", type=int, default=0)
    make_manifest.add_argument("--output", required=True)
    make_manifest.set_defaults(func=_cmd_make_manifest)

    capture_openai = sub.add_parser(
        "capture-openai",
        help="capture one live OpenAI Responses API prediction per benchmark task",
    )
    capture_openai.add_argument("--dataset", required=True)
    capture_openai.add_argument("--system-id", required=True, choices=["B0", "B1", "B2", "B3", "B4"])
    capture_openai.add_argument("--model-id", required=True)
    capture_openai.add_argument("--prompt", required=True)
    capture_openai.add_argument("--output", required=True)
    capture_openai.add_argument("--receipt-bundle")
    capture_openai.add_argument("--api-key-env", default="OPENAI_API_KEY")
    capture_openai.add_argument("--responses-url", default="https://api.openai.com/v1/responses")
    capture_openai.add_argument("--timeout-s", type=float, default=120.0)
    capture_openai.add_argument("--model-parameters-json", default="{}")
    capture_openai.set_defaults(func=_cmd_capture_openai)

    preflight = sub.add_parser(
        "preflight-live",
        help="fail closed unless a B0-B4 live run is ready to start",
    )
    preflight.add_argument("--dataset", required=True)
    preflight.add_argument("--run-root", required=True)
    preflight.add_argument("--prompt-b0", required=True)
    preflight.add_argument("--prompt-b1-b3", required=True)
    preflight.add_argument("--prompt-b2-b4", required=True)
    preflight.add_argument("--receipts-b2")
    preflight.add_argument("--receipts-b3")
    preflight.add_argument("--receipts-b4")
    preflight.add_argument("--api-key-env", default="OPENAI_API_KEY")
    preflight.add_argument("--allow-missing-api-key", action="store_true")
    preflight.set_defaults(func=_cmd_preflight_live)

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

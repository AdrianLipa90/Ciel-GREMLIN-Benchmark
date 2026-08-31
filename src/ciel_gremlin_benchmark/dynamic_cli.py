from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .capture import capture_predictions
from .ciel_receipts import write_ciel_receipt_bundle
from .dataset import load_tasks
from .dynamic_live import DynamicOpenAIResponsesAdapter
from .dynamic_preflight import dynamic_preflight_live
from .openai_live import ReceiptBundleStore, UrllibOpenAIResponsesTransport


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _load_rows(path: str | Path) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, Mapping):
                raise ValueError(f"{path}:{line_no}: row must be object")
            task_id = str(raw.get("task_id") or "")
            if not task_id or task_id in out:
                raise ValueError(f"{path}:{line_no}: invalid/duplicate task_id")
            out[task_id] = raw
    return out


def _cmd_build_ciel_receipts(args: argparse.Namespace) -> int:
    tasks = load_tasks(args.dataset)
    result = write_ciel_receipt_bundle(tasks, args.output)
    _print({"status": "PASS", **result})
    return 0


def _cmd_merge_receipts(args: argparse.Namespace) -> int:
    gremlin = _load_rows(args.gremlin)
    ciel = _load_rows(args.ciel)
    if set(gremlin) != set(ciel):
        raise ValueError("GREMLIN and CIEL receipt bundles must have identical task coverage")

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for task_id in sorted(gremlin):
            g = gremlin[task_id].get("gremlin")
            c = ciel[task_id].get("ciel")
            if not isinstance(g, Mapping):
                raise ValueError(f"{task_id}: source GREMLIN bundle lacks gremlin receipt")
            if not isinstance(c, Mapping):
                raise ValueError(f"{task_id}: source CIEL bundle lacks ciel receipt")
            if gremlin[task_id].get("execution_gate") not in (None, {}, [], ""):
                raise ValueError(f"{task_id}: GREMLIN bundle contains forbidden static execution gate")
            if ciel[task_id].get("execution_gate") not in (None, {}, [], ""):
                raise ValueError(f"{task_id}: CIEL bundle contains forbidden static execution gate")
            row = {"task_id": task_id, "gremlin": dict(g), "ciel": dict(c)}
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    tmp.replace(target)
    _print({
        "status": "PASS",
        "task_count": len(gremlin),
        "output": str(target),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    })
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    report = dynamic_preflight_live(
        dataset=args.dataset,
        run_root=args.run_root,
        prompt_paths={
            "B0": args.prompt_b0,
            "B1": args.prompt_b1_b3,
            "B3": args.prompt_b1_b3,
            "B2": args.prompt_b2_b4,
            "B4": args.prompt_b2_b4,
        },
        receipt_paths={
            "B2": args.receipts_b2,
            "B3": args.receipts_b3,
            "B4": args.receipts_b4,
        },
        api_key_env=args.api_key_env,
        require_api_key=not args.allow_missing_api_key,
    )
    _print(report.to_dict())
    return 0 if report.status == "PASS" else 1


def _cmd_capture(args: argparse.Namespace) -> int:
    try:
        parameters = json.loads(args.model_parameters_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid --model-parameters-json: {exc}") from exc
    if not isinstance(parameters, dict):
        raise ValueError("--model-parameters-json must decode to an object")

    tasks = load_tasks(args.dataset)
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    store = ReceiptBundleStore.from_jsonl(args.receipt_bundle) if args.receipt_bundle else None
    transport = UrllibOpenAIResponsesTransport(
        api_key_env=args.api_key_env,
        url=args.responses_url,
        timeout_s=args.timeout_s,
    )
    adapter = DynamicOpenAIResponsesAdapter(
        system_id=args.system_id,
        model_id=args.model_id,
        prompt=prompt,
        transport=transport,
        model_parameters=parameters,
        receipt_store=store,
    )
    predictions = capture_predictions(
        tasks,
        adapter,
        args.output,
        strict_system_contract=args.system_id != "B0",
    )
    _print({
        "status": "PASS",
        "system_id": args.system_id,
        "model_id": args.model_id,
        "captured": len(predictions),
        "output": str(args.output),
        "dynamic_ciel_gate": args.system_id in {"B3", "B4"},
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ciel_gremlin_benchmark.dynamic_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    build_ciel = sub.add_parser("build-ciel-receipts")
    build_ciel.add_argument("--dataset", required=True)
    build_ciel.add_argument("--output", required=True)
    build_ciel.set_defaults(func=_cmd_build_ciel_receipts)

    merge = sub.add_parser("merge-receipts")
    merge.add_argument("--gremlin", required=True)
    merge.add_argument("--ciel", required=True)
    merge.add_argument("--output", required=True)
    merge.set_defaults(func=_cmd_merge_receipts)

    preflight = sub.add_parser("preflight-live")
    preflight.add_argument("--dataset", required=True)
    preflight.add_argument("--run-root", required=True)
    preflight.add_argument("--prompt-b0", required=True)
    preflight.add_argument("--prompt-b1-b3", required=True)
    preflight.add_argument("--prompt-b2-b4", required=True)
    preflight.add_argument("--receipts-b2", required=True)
    preflight.add_argument("--receipts-b3", required=True)
    preflight.add_argument("--receipts-b4", required=True)
    preflight.add_argument("--api-key-env", default="OPENAI_API_KEY")
    preflight.add_argument("--allow-missing-api-key", action="store_true")
    preflight.set_defaults(func=_cmd_preflight)

    capture = sub.add_parser("capture-openai")
    capture.add_argument("--dataset", required=True)
    capture.add_argument("--system-id", choices=("B0", "B1", "B2", "B3", "B4"), required=True)
    capture.add_argument("--model-id", required=True)
    capture.add_argument("--prompt", required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument("--receipt-bundle")
    capture.add_argument("--model-parameters-json", default="{}")
    capture.add_argument("--api-key-env", default="OPENAI_API_KEY")
    capture.add_argument("--responses-url", default="https://api.openai.com/v1/responses")
    capture.add_argument("--timeout-s", type=float, default=120.0)
    capture.set_defaults(func=_cmd_capture)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

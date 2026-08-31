from ciel_gremlin_benchmark.dynamic_cli import build_parser


def test_dynamic_cli_exposes_native_ciel_receipt_builder():
    args = build_parser().parse_args([
        "build-ciel-receipts",
        "--dataset", "dataset/golden_v0_1.jsonl",
        "--output", "artifacts/ciel_receipts.jsonl",
    ])
    assert args.command == "build-ciel-receipts"
    assert callable(args.func)

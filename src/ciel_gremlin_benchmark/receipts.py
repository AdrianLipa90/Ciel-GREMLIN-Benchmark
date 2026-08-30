from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    payload.pop("commitment", None)
    return {**payload, "commitment": canonical_sha256(payload)}


def verify_receipt(receipt: Mapping[str, Any]) -> bool:
    if "commitment" not in receipt:
        return False
    expected = receipt["commitment"]
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    body = dict(receipt)
    body.pop("commitment", None)
    return canonical_sha256(body) == expected

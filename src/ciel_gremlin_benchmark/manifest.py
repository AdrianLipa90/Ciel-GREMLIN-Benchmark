from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .systems import get_system_contract

RUN_MANIFEST_SCHEMA = "CIEL_GREMLIN_RUN_MANIFEST_V0_1"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    system_id: str
    dataset_sha256: str
    benchmark_commit: str
    model_provider: str
    model_id: str
    model_parameters: Mapping[str, Any]
    prompt_sha256: str
    component_commits: Mapping[str, str] = field(default_factory=dict)
    replicate: int = 0
    schema: str = RUN_MANIFEST_SCHEMA

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RunManifest":
        return cls(
            run_id=str(raw["run_id"]),
            system_id=str(raw["system_id"]),
            dataset_sha256=str(raw["dataset_sha256"]),
            benchmark_commit=str(raw["benchmark_commit"]),
            model_provider=str(raw["model_provider"]),
            model_id=str(raw["model_id"]),
            model_parameters=dict(raw.get("model_parameters") or {}),
            prompt_sha256=str(raw["prompt_sha256"]),
            component_commits={str(k): str(v) for k, v in dict(raw.get("component_commits") or {}).items()},
            replicate=int(raw.get("replicate", 0)),
            schema=str(raw.get("schema", RUN_MANIFEST_SCHEMA)),
        )

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.schema != RUN_MANIFEST_SCHEMA:
            issues.append(f"unsupported schema {self.schema!r}")
        if not self.run_id:
            issues.append("run_id is empty")
        try:
            contract = get_system_contract(self.system_id)
        except ValueError as exc:
            issues.append(str(exc))
            return issues
        if not _HEX64.fullmatch(self.dataset_sha256):
            issues.append("dataset_sha256 must be lowercase 64-hex")
        if not _HEX40.fullmatch(self.benchmark_commit):
            issues.append("benchmark_commit must be lowercase 40-hex git SHA")
        if not self.model_provider.strip():
            issues.append("model_provider is empty")
        if not self.model_id.strip():
            issues.append("model_id is empty")
        if not _HEX64.fullmatch(self.prompt_sha256):
            issues.append("prompt_sha256 must be lowercase 64-hex")
        if self.replicate < 0:
            issues.append("replicate must be >= 0")
        for name, sha in self.component_commits.items():
            if not name:
                issues.append("component commit name is empty")
            if not _HEX40.fullmatch(sha):
                issues.append(f"component {name!r} commit must be lowercase 40-hex git SHA")
        for required in contract.required_components:
            if required not in self.component_commits:
                issues.append(f"{self.system_id} requires component commit {required!r}")
        return issues

    def comparison_key(self) -> tuple[Any, ...]:
        return (
            self.dataset_sha256,
            self.benchmark_commit,
            self.model_provider,
            self.model_id,
            _canonical_bytes(dict(self.model_parameters)),
            self.replicate,
        )

    def commitment(self) -> str:
        body = asdict(self)
        return hashlib.sha256(_canonical_bytes(body)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["manifest_commitment"] = self.commitment()
        return out


def load_manifest(path: str | Path) -> RunManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = RunManifest.from_dict(raw)
    issues = manifest.validate()
    if issues:
        raise ValueError("invalid run manifest: " + "; ".join(issues))
    expected = raw.get("manifest_commitment")
    if expected is not None and expected != manifest.commitment():
        raise ValueError("run manifest commitment mismatch")
    return manifest


def audit_comparability(manifests: list[RunManifest]) -> list[str]:
    if not manifests:
        return ["no manifests supplied"]
    issues: list[str] = []
    for manifest in manifests:
        issues.extend(f"{manifest.run_id}: {issue}" for issue in manifest.validate())
    keys = {manifest.comparison_key() for manifest in manifests}
    if len(keys) != 1:
        issues.append("run manifests do not share dataset/model/parameters/benchmark_commit/replicate")

    by_component: dict[str, set[str]] = {}
    for manifest in manifests:
        for name, sha in manifest.component_commits.items():
            by_component.setdefault(name, set()).add(sha)
    for name, shas in sorted(by_component.items()):
        if len(shas) > 1:
            issues.append(f"component {name!r} differs across runs: {sorted(shas)}")
    system_ids = [manifest.system_id for manifest in manifests]
    if len(system_ids) != len(set(system_ids)):
        issues.append("duplicate system_id manifests in comparison")
    return issues

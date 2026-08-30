from ciel_gremlin_benchmark.manifest import RunManifest, audit_comparability


D = "d" * 64
P0 = "0" * 64
P1 = "1" * 64
C = "c" * 40
G = "a" * 40
CI = "b" * 40
CS = "e" * 40


def manifest(system_id: str, prompt: str, components=None, model="model-x") -> RunManifest:
    return RunManifest(
        run_id=f"run-{system_id}",
        system_id=system_id,
        dataset_sha256=D,
        benchmark_commit=C,
        model_provider="provider",
        model_id=model,
        model_parameters={"temperature": 0, "seed": 7},
        prompt_sha256=prompt,
        component_commits=components or {},
    )


def test_manifests_allow_system_specific_prompts_but_freeze_model_and_components():
    b1 = manifest("B1", P0)
    b2 = manifest("B2", P1, {"gremlin": G})
    b4 = manifest("B4", "2" * 64, {"gremlin": G, "cielingo": CI, "ciel_semantic": CS})
    assert audit_comparability([b1, b2, b4]) == []


def test_manifest_audit_rejects_model_drift():
    b1 = manifest("B1", P0)
    b2 = manifest("B2", P1, {"gremlin": G}, model="other-model")
    issues = audit_comparability([b1, b2])
    assert any("do not share" in issue for issue in issues)


def test_b4_manifest_requires_all_component_commits():
    b4 = manifest("B4", P1, {"gremlin": G})
    issues = b4.validate()
    assert any("cielingo" in issue for issue in issues)
    assert any("ciel_semantic" in issue for issue in issues)

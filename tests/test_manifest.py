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


def test_manifests_allow_layer_specific_prompts_with_paired_ablation_prompts():
    b1 = manifest("B1", P0)
    b2 = manifest("B2", P1, {"gremlin": G})
    b3 = manifest("B3", P0, {"cielingo": CI, "ciel_semantic": CS})
    b4 = manifest(
        "B4",
        P1,
        {"gremlin": G, "cielingo": CI, "ciel_semantic": CS},
    )
    assert audit_comparability([b1, b2, b3, b4]) == []


def test_manifest_audit_rejects_model_drift():
    b1 = manifest("B1", P0)
    b2 = manifest("B2", P1, {"gremlin": G}, model="other-model")
    issues = audit_comparability([b1, b2])
    assert any("do not share" in issue for issue in issues)


def test_manifest_audit_rejects_b1_b3_prompt_drift():
    b1 = manifest("B1", P0)
    b3 = manifest("B3", P1, {"cielingo": CI, "ciel_semantic": CS})
    issues = audit_comparability([b1, b3])
    assert any("B1 and B3" in issue for issue in issues)


def test_manifest_audit_rejects_b2_b4_prompt_drift():
    b2 = manifest("B2", P0, {"gremlin": G})
    b4 = manifest(
        "B4",
        P1,
        {"gremlin": G, "cielingo": CI, "ciel_semantic": CS},
    )
    issues = audit_comparability([b2, b4])
    assert any("B2 and B4" in issue for issue in issues)


def test_b4_manifest_requires_all_component_commits():
    b4 = manifest("B4", P1, {"gremlin": G})
    issues = b4.validate()
    assert any("cielingo" in issue for issue in issues)
    assert any("ciel_semantic" in issue for issue in issues)

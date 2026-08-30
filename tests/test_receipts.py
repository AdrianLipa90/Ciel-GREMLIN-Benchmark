from ciel_gremlin_benchmark.receipts import canonical_sha256, seal_receipt, verify_receipt


def test_receipt_commitment_is_deterministic():
    a = {"operator": "GIVES", "ports": {"DAT": "Zosia", "ACC": "book"}}
    b = {"ports": {"ACC": "book", "DAT": "Zosia"}, "operator": "GIVES"}
    assert canonical_sha256(a) == canonical_sha256(b)


def test_sealed_receipt_verifies_and_mutation_fails():
    receipt = seal_receipt({"schema": "TEST", "status": "PASS"})
    assert verify_receipt(receipt)

    forged = dict(receipt)
    forged["status"] = "FAIL"
    assert not verify_receipt(forged)

"""The chained log and the Merkle tree: what makes a campaign verifiable offline."""

from __future__ import annotations

import json

import pytest

from rimi_tests import proof


def record(index: int) -> dict:
    return {"execution": index, "request_sha256": "a" * 64, "response_sha256": "b" * 64,
            "model": "example/model-1", "tokens": {"input": 10, "output": 20}}


def test_chain_links_records_in_order(tmp_path):
    log = proof.ChainLog(tmp_path / "chain.jsonl")
    first = log.append(record(0))
    second = log.append(record(1))
    assert first["prev_sha256"] == proof.GENESIS
    assert second["prev_sha256"] == first["record_sha256"]
    assert proof.verify_chain(log.records()).ok


def test_removing_a_record_breaks_the_chain(tmp_path):
    path = tmp_path / "chain.jsonl"
    log = proof.ChainLog(path)
    for i in range(3):
        log.append(record(i))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    verdict = proof.verify_chain(log.records())
    assert not verdict.ok and verdict.broken_at == 1


def test_rewriting_a_record_breaks_its_own_hash(tmp_path):
    path = tmp_path / "chain.jsonl"
    log = proof.ChainLog(path)
    log.append(record(0))
    log.append(record(1))
    records = log.records()
    records[1]["tokens"]["output"] = 1
    verdict = proof.verify_chain(records)
    assert not verdict.ok and verdict.broken_at == 1


def test_a_record_that_looks_like_a_key_is_refused(tmp_path):
    log = proof.ChainLog(tmp_path / "chain.jsonl")
    with pytest.raises(proof.SecretInRecordError):
        log.append({"headers": {"authorization": "Bearer abc"}})
    assert not (tmp_path / "chain.jsonl").exists()


def test_canonical_json_is_stable():
    assert proof.canonical_json({"b": 1, "a": [2, 3]}) == '{"a":[2,3],"b":1}'
    assert proof.sha256_canonical({"a": 1, "b": 2}) == proof.sha256_canonical({"b": 2, "a": 1})


def test_merkle_root_and_paths():
    leaves = [proof.sha256_text(str(i)) for i in range(5)]
    root = proof.merkle_root(leaves)
    assert len(root) == 64
    for index, leaf in enumerate(leaves):
        path = proof.merkle_path(leaves, index)
        assert proof.verify_merkle_path(leaf, path, root), index
    assert proof.merkle_root([]) == proof.GENESIS
    assert proof.merkle_root(leaves[:1]) == leaves[0]


def test_bundle_layout_is_the_one_of_the_specification(tmp_path):
    paths = proof.bundle_paths(tmp_path / "2026-09-20")
    assert paths["bundle"].name == "proof-bundle"
    assert {p.name for p in paths.values()} >= {
        "manifest.json", "chain.jsonl", "merkle.json", "raw", "report.json",
        "signature.sig", "pubkey.pem", "VERIFY.md",
    }


def test_chain_file_is_append_only_jsonl(tmp_path):
    path = tmp_path / "chain.jsonl"
    log = proof.ChainLog(path)
    log.append(record(0))
    log.append(record(1))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["record_sha256"] for line in lines)

"""Hashes, append-only chained log and Merkle root — the base of the self-proof bundle.

A campaign must be verifiable offline, by someone who trusts neither rimi. nor the
declarant (specification §13). The pieces are laid down here from the start, so that
the run directory has the right shape long before the full `rimi verify` arrives (T7):

    runs/<date>/proof-bundle/
        manifest.json     the campaign as announced, before execution
        chain.jsonl       one record per model call, each carrying the previous hash
        merkle.json       Merkle root and paths for the transcripts
        raw/              raw transcripts, or their hashes when redacted
        report.json       the report, with the expected and the realised counts
        signature.sig     signature of the declarant
        pubkey.pem        the matching public key
        VERIFY.md         how to verify, in three commands

Only hashes are ever anchored, never content: nothing personal reaches a public log.
An API key must never be written to a record — `chain_record()` refuses obvious ones.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROOF_BUNDLE_DIR = "proof-bundle"
MANIFEST_FILE = "manifest.json"
CHAIN_FILE = "chain.jsonl"
MERKLE_FILE = "merkle.json"
RAW_DIR = "raw"
REPORT_FILE = "report.json"
SIGNATURE_FILE = "signature.sig"
PUBKEY_FILE = "pubkey.pem"
VERIFY_FILE = "VERIFY.md"

GENESIS = "0" * 64

# Key-shaped strings that must never end up in a record.
_SECRET_HINTS = ("sk-", "api_key", "apikey", "authorization", "bearer ", "secret")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(value: Any) -> str:
    """Stable JSON: sorted keys, no spare whitespace. Same input, same bytes, always."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_canonical(value: Any) -> str:
    return sha256_text(canonical_json(value))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class SecretInRecordError(ValueError):
    """Raised when a record looks like it carries a credential."""


def _assert_no_secret(record: dict[str, Any]) -> None:
    blob = canonical_json(record).lower()
    for hint in _SECRET_HINTS:
        if hint in blob:
            raise SecretInRecordError(
                f"the record contains {hint!r}: keys and headers never go into the chain"
            )


def chain_record(record: dict[str, Any], previous_sha256: str = GENESIS) -> dict[str, Any]:
    """Return `record` sealed: previous hash added, then its own hash over the whole."""
    _assert_no_secret(record)
    sealed = dict(record)
    sealed["prev_sha256"] = previous_sha256
    sealed["record_sha256"] = sha256_canonical(sealed)
    return sealed


@dataclass
class ChainLog:
    """Append-only JSONL log. Removing or rewriting a line breaks the chain."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    def last_hash(self) -> str:
        last = GENESIS
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        last = json.loads(line)["record_sha256"]
        return last

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        sealed = chain_record(record, self.last_hash())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(sealed) + "\n")
        return sealed

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


@dataclass
class ChainVerdict:
    ok: bool
    count: int
    broken_at: int | None = None
    reason: str | None = None


def verify_chain(records: list[dict[str, Any]]) -> ChainVerdict:
    """Check every link and every record hash. Says where it breaks, not just that it does."""
    previous = GENESIS
    for position, record in enumerate(records):
        if record.get("prev_sha256") != previous:
            return ChainVerdict(False, len(records), position, "previous hash does not match")
        body = {k: v for k, v in record.items() if k != "record_sha256"}
        if sha256_canonical(body) != record.get("record_sha256"):
            return ChainVerdict(False, len(records), position, "record hash does not match its content")
        previous = record["record_sha256"]
    return ChainVerdict(True, len(records))


def merkle_root(leaves: list[str]) -> str:
    """Merkle root of hex hashes. An odd node is carried up, not duplicated."""
    if not leaves:
        return GENESIS
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(sha256_text(level[i] + level[i + 1]))
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def merkle_path(leaves: list[str], index: int) -> list[dict[str, str]]:
    """Sibling hashes proving that `leaves[index]` belongs to the tree."""
    if not leaves or not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    path: list[dict[str, str]] = []
    level, position = list(leaves), index
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            left, right = level[i], level[i + 1]
            if i == position - (position % 2) and position < len(level) - (len(level) % 2):
                path.append({"side": "right" if position % 2 == 0 else "left",
                             "sha256": right if position % 2 == 0 else left})
            nxt.append(sha256_text(left + right))
        if len(level) % 2:
            nxt.append(level[-1])
        position //= 2
        level = nxt
    return path


def verify_merkle_path(leaf: str, path: list[dict[str, str]], root: str) -> bool:
    current = leaf
    for step in path:
        current = (sha256_text(step["sha256"] + current) if step["side"] == "left"
                   else sha256_text(current + step["sha256"]))
    return current == root


def bundle_paths(run_dir: str | Path) -> dict[str, Path]:
    """The layout of a proof bundle. Written here once, used everywhere else."""
    base = Path(run_dir) / PROOF_BUNDLE_DIR
    return {
        "bundle": base,
        "manifest": base / MANIFEST_FILE,
        "chain": base / CHAIN_FILE,
        "merkle": base / MERKLE_FILE,
        "raw": base / RAW_DIR,
        "report": base / REPORT_FILE,
        "signature": base / SIGNATURE_FILE,
        "pubkey": base / PUBKEY_FILE,
        "verify": base / VERIFY_FILE,
    }

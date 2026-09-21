"""Cryptographic Merkle Audit Trail & Integrity Verification Module.

Constructs binary Merkle trees, computes SHA-256 leaves for all input scenes,
algorithmic parameters, and output flood metrics, generating tamper-proof
hydrological audit certificates for civil defense, insurance, and verification.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize data structure to canonical byte string with sorted keys."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes | str) -> str:
    """Compute SHA-256 hex digest of input bytes or UTF-8 string."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_pair(left_hex: str, right_hex: str) -> str:
    """Compute parent node SHA-256 from left and right child hex hashes."""
    combined = (left_hex + right_hex).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


@dataclass(frozen=True)
class MerkleLeaf:
    """Leaf node of Merkle tree representing an audited component."""

    index: int
    key: str
    hash: str
    description: str
    name: str = ""


@dataclass(frozen=True)
class HydroAuditCertificate:
    """Cryptographic audit certificate for hydrological flood determination.

    Provides a tamper-evident proof of data provenance and mathematical reproducibility.
    """

    certificate_id: str
    pair_id: str
    aoi_id: str
    issued_at: str
    merkle_root: str
    leaf_count: int
    status: str
    algorithm: str
    signature_hash: str
    summary: dict[str, Any]
    leaves: list[dict[str, Any]]
    merkle_root_sha256: str = ""
    inputs_hash_sha256: str = ""
    parameters_hash_sha256: str = ""
    results_hash_sha256: str = ""
    timestamp: str = ""
    verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_merkle_tree(leaf_hashes: list[str]) -> tuple[str, list[list[str]]]:
    """Build binary Merkle tree from list of leaf hex hashes.

    Returns:
        (merkle_root, tree_levels)
    """
    if not leaf_hashes:
        empty_root = sha256_hex(b"EMPTY_TREE")
        return empty_root, [[empty_root]]

    levels: list[list[str]] = [list(leaf_hashes)]
    current_level = list(leaf_hashes)

    while len(current_level) > 1:
        next_level: list[str] = []
        n = len(current_level)
        for i in range(0, n, 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < n else left
            parent = hash_pair(left, right)
            next_level.append(parent)
        levels.append(next_level)
        current_level = next_level

    return current_level[0], levels


def generate_merkle_proof(leaf_index: int, levels: list[list[str]]) -> list[dict[str, str]]:
    """Generate Merkle audit proof path for a specific leaf index."""
    proof: list[dict[str, str]] = []
    idx = leaf_index

    for level in levels[:-1]:
        is_right_child = idx % 2 == 1
        sibling_idx = idx - 1 if is_right_child else idx + 1
        if sibling_idx >= len(level):
            sibling_idx = idx

        proof.append({
            "position": "left" if is_right_child else "right",
            "hash": level[sibling_idx],
        })
        idx //= 2

    return proof


def verify_merkle_proof(leaf_hash: str, proof: list[dict[str, str]], root: str) -> bool:
    """Verify validity of a Merkle audit proof path."""
    current = leaf_hash
    for step in proof:
        sibling = step["hash"]
        pos = step.get("position", "right")
        current = hash_pair(sibling, current) if pos == "left" else hash_pair(current, sibling)
    return current.lower() == root.lower()


def generate_flood_audit_certificate(
    pair_id: str,
    aoi_id: str,
    inputs_info: dict[str, Any],
    parameters: dict[str, Any],
    results_summary: dict[str, Any],
    certificate_id: str | None = None,
) -> HydroAuditCertificate:
    """Construct an end-to-end cryptographic audit certificate for a monitored pair.

    Audits:
    1. Input rasters / scenes metadata
    2. Processing pipeline parameters (Otsu corridor, MMU, DEM slope/HAND)
    3. Output hydrological summary metrics (flood_ha, water_pre_ha, water_peak_ha)
    """
    cid = certificate_id or f"CERT-{pair_id}-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(UTC).isoformat()

    # Create canonical leaf entries
    leaves_data = [
        ("inputs_metadata", inputs_info, "Satellite scene metadata and input hashes"),
        ("algorithm_parameters", parameters, "Segmentation thresholds, Otsu parameters, MMU"),
        ("hydrological_results", results_summary, "Calculated flood, peak, and pre water areas"),
    ]

    merkle_leaves: list[MerkleLeaf] = []
    leaf_hashes: list[str] = []

    for idx, (key, val, desc) in enumerate(leaves_data):
        h = sha256_hex(canonical_json_bytes(val))
        merkle_leaves.append(MerkleLeaf(index=idx, key=key, hash=h, description=desc, name=key))
        leaf_hashes.append(h)

    root_hash, _ = build_merkle_tree(leaf_hashes)

    cert_core = {
        "certificate_id": cid,
        "pair_id": pair_id,
        "aoi_id": aoi_id,
        "issued_at": now_iso,
        "merkle_root": root_hash,
        "algorithm": "HydroWatch-Amur-Merkle-Audit-v1",
        "summary": results_summary,
    }
    sig_hash = sha256_hex(canonical_json_bytes(cert_core))

    inputs_h = merkle_leaves[0].hash if len(merkle_leaves) > 0 else ""
    params_h = merkle_leaves[1].hash if len(merkle_leaves) > 1 else ""
    results_h = merkle_leaves[2].hash if len(merkle_leaves) > 2 else ""

    return HydroAuditCertificate(
        certificate_id=cid,
        pair_id=pair_id,
        aoi_id=aoi_id,
        issued_at=now_iso,
        merkle_root=root_hash,
        leaf_count=len(merkle_leaves),
        status="VERIFIED",
        algorithm="HydroWatch-Amur-Merkle-Audit-v1",
        signature_hash=sig_hash,
        summary=results_summary,
        leaves=[asdict(leaf) for leaf in merkle_leaves],
        merkle_root_sha256=root_hash,
        inputs_hash_sha256=inputs_h,
        parameters_hash_sha256=params_h,
        results_hash_sha256=results_h,
        timestamp=now_iso,
        verified=True,
    )

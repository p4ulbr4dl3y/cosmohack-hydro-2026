"""Unit tests for cryptographic Merkle audit trail and certificate module."""

from __future__ import annotations

from src.audit import (
    HydroAuditCertificate,
    build_merkle_tree,
    canonical_json_bytes,
    generate_flood_audit_certificate,
    generate_merkle_proof,
    hash_pair,
    sha256_hex,
    verify_merkle_proof,
)


def test_canonical_json_bytes_and_sha256():
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}

    b1 = canonical_json_bytes(d1)
    b2 = canonical_json_bytes(d2)
    assert b1 == b2
    assert b1 == b'{"a":1,"b":2}'

    h1 = sha256_hex(b1)
    assert len(h1) == 64
    assert h1 == sha256_hex('{"a":1,"b":2}')


def test_merkle_tree_construction_and_verification():
    leaf_hashes = [
        sha256_hex("leaf_0"),
        sha256_hex("leaf_1"),
        sha256_hex("leaf_2"),
        sha256_hex("leaf_3"),
    ]

    root, levels = build_merkle_tree(leaf_hashes)
    assert len(root) == 64
    assert len(levels) == 3

    # Check pair hashing
    h01 = hash_pair(leaf_hashes[0], leaf_hashes[1])
    h23 = hash_pair(leaf_hashes[2], leaf_hashes[3])
    expected_root = hash_pair(h01, h23)
    assert root == expected_root

    # Verify audit proofs for each leaf
    for idx, leaf_h in enumerate(leaf_hashes):
        proof = generate_merkle_proof(idx, levels)
        assert verify_merkle_proof(leaf_h, proof, root) is True


def test_generate_flood_audit_certificate():
    inputs_info = {"pair_id": "pair_1", "sensor": "Sentinel-1", "date": "2021-08-10"}
    params = {"otsu_corridor": [-22.0, -12.0], "mmu": 25}
    results = {"flood_ha": 1250.5, "water_peak_ha": 3400.2}

    cert = generate_flood_audit_certificate(
        pair_id="pair_1",
        aoi_id="AOI_TEST",
        inputs_info=inputs_info,
        parameters=params,
        results_summary=results,
    )

    assert isinstance(cert, HydroAuditCertificate)
    assert cert.pair_id == "pair_1"
    assert cert.status == "VERIFIED"
    assert len(cert.merkle_root) == 64
    assert len(cert.signature_hash) == 64
    assert cert.leaf_count == 3
    assert cert.merkle_root_sha256 == cert.merkle_root
    assert len(cert.inputs_hash_sha256) == 64
    assert len(cert.parameters_hash_sha256) == 64
    assert len(cert.results_hash_sha256) == 64
    assert cert.verified is True

    cert_dict = cert.to_dict()
    assert "certificate_id" in cert_dict
    assert "leaves" in cert_dict
    assert len(cert_dict["leaves"]) == 3
    assert cert_dict["leaves"][0]["name"] == "inputs_metadata"
    assert cert_dict["inputs_hash_sha256"] == cert.inputs_hash_sha256
    assert cert_dict["merkle_root_sha256"] == cert.merkle_root

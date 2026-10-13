# -*- coding: utf-8 -*-
"""Unit tests for Logic Manifest Governance & CI Hash Verification (TASK-0085)."""

import json
from pathlib import Path

from logic_manifest import (
    DECISION_CRITICAL_FILES,
    LOGIC_VERSION,
    build_logic_manifest,
    compute_file_sha256,
    verify_logic_manifest,
)


def test_decision_critical_files_exist_and_hashable():
    """Verify that every decision-critical file exists and has valid SHA256."""
    for rel_path in DECISION_CRITICAL_FILES:
        p = Path(rel_path)
        assert p.exists(), f"Missing decision-critical file: {rel_path}"
        sha = compute_file_sha256(p)
        assert len(sha) == 64, f"Invalid SHA256 length for {rel_path}"


def test_logic_manifest_matches_committed_state():
    """Verify that current codebase matches committed logic_manifest.json."""
    is_valid, violations = verify_logic_manifest()
    assert is_valid, f"Logic manifest verification failed with violations: {violations}"


def test_ci_fails_if_decision_critical_file_tampered_without_version_bump(tmp_path):
    """Verify that modifying any logic file without bumping logic_version raises violation."""
    manifest_file = tmp_path / "mock_manifest.json"
    manifest = build_logic_manifest()
    # Save legitimate manifest
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Simulate tampered file by tweaking stored hash
    tampered_manifest = dict(manifest)
    tampered_files = dict(tampered_manifest["file_hashes"])
    tampered_files["quant_valuation.py"] = "0" * 64
    tampered_manifest["file_hashes"] = tampered_files
    tampered_manifest["manifest_hash"] = "tampered_hash_123"

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(tampered_manifest, f)

    is_valid, violations = verify_logic_manifest(manifest_path=manifest_file)
    assert not is_valid
    assert any("BUILD HASH MISMATCH" in v or "MISMATCH" in v for v in violations)


def test_logic_version_exported():
    """Verify LOGIC_VERSION is non-empty and starts with v15."""
    assert LOGIC_VERSION.startswith("v15.0")


def test_effective_config_and_universe_hashes():
    """Verify effective_config_hash and universe_hash are generated and non-empty."""
    from logic_manifest import compute_effective_config_hash, compute_universe_hash

    cfg_h = compute_effective_config_hash()
    univ_h = compute_universe_hash()
    assert len(cfg_h) == 16
    assert len(univ_h) == 16

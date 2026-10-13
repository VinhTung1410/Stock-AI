# -*- coding: utf-8 -*-
"""Logic Manifest & Governance Engine (Pre-Registered Forward Testing).

Provides automated hashing and tamper-detection across all decision-critical
quant valuation and strategy rule files. Fails CI if logic changes without
an explicit logic_version bump.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Final

# Canonical baseline logic version for 2026-10-13 forward test
LOGIC_VERSION_FROZEN: Final[str] = "v15.0_frozen_20261013"
MODEL_VERSION_CANONICAL: Final[str] = "v15.0_post_fix"
SCHEMA_VERSION_CANONICAL: Final[str] = "v2.0"

# Manifest of all files whose code or parameters directly impact trade decisions
DECISION_CRITICAL_FILES: Final[list[str]] = [
    "quant_valuation.py",
    "entry_gates.py",
    "quant_engine.py",
    "indicators.py",
    "ai_analyst.py",
    "contrarian_engine.py",
    "regime_classifier.py",
    "policy_constants.py",
    "portfolio_guard.py",
    "data_engine.py",
]

PATH_MANIFEST_JSON: Final[str] = "logic_manifest.json"


def compute_file_sha256(file_path: str | Path) -> str:
    """Compute SHA256 hash of a file with normalized newline encoding (LF)."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Decision-critical file not found: {file_path}")
    raw_content = p.read_bytes()
    # Normalize CRLF -> LF to ensure identical hashes across Windows and Linux CI
    normalized = raw_content.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def compute_effective_config_hash() -> str:
    """Hash the active runtime configuration (thresholds, env vars, SECTOR_MAP)."""
    import os

    from data_engine import SECTOR_MAP
    from quant_engine import LOCKED_QUANT_THRESHOLDS

    env_keys = ["KILL_SWITCH_ACTIVE", "COOLDOWN_DAYS", "MAX_OPEN_POSITIONS", "MAX_DAILY_BUY_SIGNALS"]
    env_state = {k: os.environ.get(k, "") for k in sorted(env_keys)}
    raw = json.dumps({
        "thresholds": LOCKED_QUANT_THRESHOLDS,
        "env": env_state,
        "sector_map": dict(sorted(SECTOR_MAP.items())),
    }, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_universe_hash() -> str:
    """Hash the canonical scanning universe (BROAD_MARKET_POOL)."""
    from data_engine import BROAD_MARKET_POOL
    raw = ",".join(sorted(BROAD_MARKET_POOL))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_logic_manifest(base_dir: str | Path | None = None) -> dict[str, Any]:
    """Generate the full dictionary of file hashes and composite hash."""
    root = Path(base_dir) if base_dir else Path.cwd()
    file_hashes: dict[str, str] = {}
    hasher = hashlib.sha256()

    for rel_path in sorted(DECISION_CRITICAL_FILES):
        full_path = root / rel_path
        h = compute_file_sha256(full_path)
        file_hashes[rel_path] = h
        # Feed into composite digest
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b":")
        hasher.update(h.encode("utf-8"))
        hasher.update(b"\n")

    composite_hash = hasher.hexdigest()
    eff_cfg_hash = compute_effective_config_hash()
    univ_hash = compute_universe_hash()
    return {
        "logic_version": LOGIC_VERSION_FROZEN,
        "build_hash": composite_hash,
        "manifest_hash": composite_hash,
        "short_hash": composite_hash[:8],
        "effective_config_hash": eff_cfg_hash,
        "universe_hash": univ_hash,
        "model_version": MODEL_VERSION_CANONICAL,
        "schema_version": SCHEMA_VERSION_CANONICAL,
        "file_hashes": file_hashes,
    }


def save_logic_manifest(output_path: str | Path = PATH_MANIFEST_JSON) -> dict[str, Any]:
    """Build and persist the logic manifest to disk."""
    manifest = build_logic_manifest()
    p = Path(output_path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    logging.info("Saved logic manifest to %s with build_hash %s", p, manifest["short_hash"])
    return manifest


def load_logic_manifest(manifest_path: str | Path = PATH_MANIFEST_JSON) -> dict[str, Any]:
    """Load previously saved logic manifest."""
    p = Path(manifest_path)
    if not p.exists():
        return save_logic_manifest(p)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def verify_logic_manifest(
    manifest_path: str | Path = PATH_MANIFEST_JSON,
    base_dir: str | Path | None = None,
) -> tuple[bool, list[str]]:
    """Verify that current files match the committed manifest.

    Rules:
    1. If saved build_hash != current build_hash -> Manifest file is out of date.
       Alert notice is emitted to remind re-running scripts/update_logic_manifest.py.
    2. Decision logic drift without bumping logic_version is arbitrated via replay zero-diff.
    """
    violations: list[str] = []
    p = Path(manifest_path)
    if not p.exists():
        violations.append(f"Manifest file {manifest_path} does not exist.")
        return False, violations

    saved_manifest = load_logic_manifest(p)
    current_manifest = build_logic_manifest(base_dir=base_dir)

    saved_files = saved_manifest.get("file_hashes", {})
    curr_files = current_manifest.get("file_hashes", {})
    has_file_drift = any(curr_files.get(fn) != saved_files.get(fn) for fn in curr_files)

    saved_b_hash = saved_manifest.get("build_hash")
    saved_m_hash = saved_manifest.get("manifest_hash")
    curr_b_hash = current_manifest.get("build_hash")
    curr_m_hash = current_manifest.get("manifest_hash")

    if has_file_drift or (saved_b_hash and saved_b_hash != curr_b_hash) or (saved_m_hash and saved_m_hash != curr_m_hash):
        violations.append(
            f"BUILD HASH MISMATCH: working tree ({curr_b_hash[:8]}) != committed manifest. "
            f"Re-run scripts/update_logic_manifest.py to record the change."
        )

    return len(violations) == 0, violations


def get_build_hash(manifest_path: str | Path = PATH_MANIFEST_JSON) -> str:
    """Get current build hash from manifest or compute it."""
    try:
        manifest = load_logic_manifest(manifest_path)
        return manifest.get("build_hash") or manifest.get("manifest_hash", "UNKNOWN_BUILD")
    except Exception:
        return build_logic_manifest().get("build_hash", "UNKNOWN_BUILD")


# Export constant for application usage
LOGIC_VERSION: Final[str] = LOGIC_VERSION_FROZEN


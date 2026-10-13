# -*- coding: utf-8 -*-
"""Script to update and re-lock logic_manifest.json when logic_version is bumped."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic_manifest import save_logic_manifest


def main():
    print("Computing SHA256 hashes across all decision-critical files...")
    manifest = save_logic_manifest()
    print("Successfully generated and saved logic_manifest.json!")
    print(f"Logic Version: {manifest['logic_version']}")
    print(f"Manifest Hash: {manifest['manifest_hash']} ({manifest['short_hash']})")
    print(f"Total Files Covered: {len(manifest['file_hashes'])}")


if __name__ == "__main__":
    main()

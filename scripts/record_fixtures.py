"""
Script to record and inspect static offline financial fixtures (TASK-0072).
Used to snapshot real financial data from local files or data engine for reproducible golden testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def save_fixture(symbol: str, data: Dict[str, Any], filename: str) -> Path:
    """Save an immutable JSON snapshot fixture."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIXTURES_DIR / filename
    payload = dict(data)
    payload["symbol"] = symbol.upper()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def load_fixture(filename: str) -> Dict[str, Any]:
    """Load a fixture from disk."""
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    print(f"Fixtures directory: {FIXTURES_DIR}")
    for item in FIXTURES_DIR.glob("*.json"):
        d = load_fixture(item.name)
        print(f"  - {item.name}: {d.get('symbol')} ({d.get('period')}) - Price: {d.get('price')}")

"""Stock-AI test suite configuration."""
import os
import sys
from unittest.mock import patch

import pytest

# Guard against Windows AppLocker / WDAC blocking pyarrow DLL
try:
    import pyarrow.compute  # noqa: F401
except (ImportError, Exception):
    sys.modules["pyarrow"] = None

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mark test environment explicitly
os.environ["ENV"] = "testing"


@pytest.fixture(autouse=True)
def prevent_accidental_db_writes(request):
    """Prevent offline/unit tests from accidentally writing to live Supabase database.
    Only tests explicitly marked with @pytest.mark.integration can perform live DB operations.
    """
    if "integration" in request.keywords:
        yield
        return

    try:
        with patch("db_manager.save_quant_signal", return_value=999999), \
             patch("db_manager.save_decision_record", return_value=True), \
             patch("db_manager.save_signal_lifecycle", return_value=True):
            yield
    except ImportError:
        yield

"""Shared test setup: any real Firestore call from a test is a bug (it would hit the live project)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def no_live_firestore(monkeypatch):
    import firestore_auth

    def _blocked(*args, **kwargs):
        raise AssertionError("test tried to open a real Firestore session; fake firestore_auth.session instead")

    monkeypatch.setattr(firestore_auth, "session", _blocked)

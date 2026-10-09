import os
import sys
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test talks to the real network: every call goes through an injected opener."""
    def blocked(*args, **kwargs):
        raise AssertionError("a test tried to open the network")
    monkeypatch.setattr(urllib.request, "urlopen", blocked)


@pytest.fixture(autouse=True)
def no_real_login(monkeypatch, tmp_path):
    """No test reads the real `claude` login: the config dir points at an empty tmp dir."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_dir(d: Path) -> dict[str, bytes]:
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep every test away from the real data, cache and profile dirs, and off the network."""
    monkeypatch.setenv("SKILLSCOUT_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("SKILLSCOUT_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("SKILLSCOUT_PROFILE", str(tmp_path / "profile.yaml"))
    monkeypatch.delenv("SKILLS_SH_TOKEN", raising=False)

    def no_network(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    return tmp_path

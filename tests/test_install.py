import hashlib
import json

import pytest

from skillscout import github, install, vet
from skillscout.config import data_dir

SHA = "c" * 40


def stage(verdict="PASS", content=b"---\nname: demo\n---\nhi\n"):
    """Pretend `vet` already fetched and scanned o/r/demo at SHA."""
    store = data_dir() / "files" / vet.slug("o/r/demo") / SHA
    store.mkdir(parents=True)
    (store / "SKILL.md").write_bytes(content)
    vet.write_report({"id": "o/r/demo", "source": "o/r", "skill_dir": "demo", "sha": SHA, "licence": "MIT",
                      "verdict": verdict, "findings": [],
                      "files": {"SKILL.md": hashlib.sha256(content).hexdigest()}})
    return store


@pytest.fixture
def fake_github(monkeypatch):
    state = {"head": SHA, "tree": "t1"}
    monkeypatch.setattr(github, "dir_tree_sha", lambda s, sha, d: "t1" if sha == SHA else state["tree"])
    monkeypatch.setattr(github, "repo_meta", lambda s: {"default_branch": "main"})
    monkeypatch.setattr(github, "head_sha", lambda s, b: state["head"])
    return state


def test_install_copies_pinned_files_and_registers(isolated_home, fake_github):
    stage()
    dest = install.install("o/r/demo", isolated_home / "skills")
    assert (dest / "SKILL.md").read_text().startswith("---")
    reg = json.loads(install.registry_path().read_text())
    assert reg["o/r/demo"]["sha"] == SHA and "SKILL.md" in reg["o/r/demo"]["files"]


def test_install_refuses_fail_and_unaccepted_review(isolated_home, fake_github):
    stage("FAIL")
    with pytest.raises(SystemExit, match="failed vetting"):
        install.install("o/r/demo", isolated_home / "skills")
    vet.write_report({**vet.load_report("o/r/demo"), "verdict": "REVIEW"})
    with pytest.raises(SystemExit, match="needs review"):
        install.install("o/r/demo", isolated_home / "skills")
    assert install.install("o/r/demo", isolated_home / "skills", allow_review=True).exists()


def test_install_refuses_tampered_store_and_existing_dest(isolated_home, fake_github):
    store = stage()
    (store / "SKILL.md").write_text("tampered")
    with pytest.raises(SystemExit, match="no longer matches"):
        install.install("o/r/demo", isolated_home / "skills")
    (store / "SKILL.md").write_bytes(b"---\nname: demo\n---\nhi\n")
    (isolated_home / "skills" / "demo").mkdir(parents=True)
    with pytest.raises(SystemExit, match="already exists"):
        install.install("o/r/demo", isolated_home / "skills")


def test_install_without_vet_report_refused(isolated_home):
    with pytest.raises(SystemExit, match="No vet report"):
        install.install("o/r/nothing", isolated_home / "skills")


def test_check_updates_flags_upstream_and_drift(isolated_home, fake_github):
    stage()
    dest = install.install("o/r/demo", isolated_home / "skills")
    assert install.check_updates()[0]["upstream_changed"] is False
    fake_github["head"] = "d" * 40          # new commit elsewhere in the repo: not a change
    assert install.check_updates()[0]["upstream_changed"] is False
    fake_github["tree"] = "t2"              # skill dir itself changed
    (dest / "SKILL.md").write_text("edited locally")
    row = install.check_updates()[0]
    assert row["upstream_changed"] is True and row["local_drift"] == ["SKILL.md"]

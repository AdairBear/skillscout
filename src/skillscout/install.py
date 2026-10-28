"""Explicit install of a vetted, pinned skill, a hash registry, and upstream change checks. No auto-update."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import github
from .config import data_dir
from .vet import load_report, slug


def registry_path() -> Path:
    return data_dir() / "registry.json"


def load_registry() -> dict:
    p = registry_path()
    return json.loads(p.read_text()) if p.exists() else {}


def _save_registry(reg: dict) -> None:
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text(json.dumps(reg, indent=1, sort_keys=True))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def install(skill_id: str, dest_root: Path, allow_review: bool = False) -> Path:
    """Copy exactly the bytes that were vetted. Refuses FAIL, and REVIEW unless allow_review."""
    r = load_report(skill_id)
    if r is None:
        raise SystemExit(f"No vet report for {skill_id}. Run `skillscout vet` first.")
    if r["verdict"] == "FAIL":
        raise SystemExit(f"{skill_id} failed vetting; not installing. See its vet report.")
    if r["verdict"] == "REVIEW" and not allow_review:
        raise SystemExit(f"{skill_id} needs review. Read its vet report, then rerun with --accept-review.")
    store = data_dir() / "files" / slug(skill_id) / r["sha"]
    for rel, want in r["files"].items():
        if _sha256(store / rel) != want:
            raise SystemExit(f"Stored file {rel} no longer matches its vetted hash; re-vet.")
    name = skill_id.rsplit("/", 1)[1]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise SystemExit(f"Refusing unsafe skill name {name!r}.")
    dest = dest_root / name
    if dest.exists():
        raise SystemExit(f"{dest} already exists; not overwriting.")
    dest.mkdir(parents=True)
    for rel in r["files"]:
        target = dest / rel
        if not target.resolve().is_relative_to(dest.resolve()):
            raise SystemExit(f"Refusing path outside the skill dir: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(store / rel, target)  # copyfile drops exec bits on purpose
    reg = load_registry()
    reg[skill_id] = {
        "source": r["source"], "skill_dir": r["skill_dir"], "sha": r["sha"], "verdict": r["verdict"],
        "dir_tree_sha": github.dir_tree_sha(r["source"], r["sha"], r["skill_dir"]),
        "path": str(dest), "files": r["files"],
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save_registry(reg)
    return dest


def check_updates() -> list[dict]:
    """Flag upstream changes and local drift. Never pulls anything."""
    out = []
    for sid, e in load_registry().items():
        row = {"id": sid, "pinned": e["sha"][:12], "upstream_changed": None, "local_drift": []}
        for rel, want in e["files"].items():
            p = Path(e["path"]) / rel
            if not p.exists() or _sha256(p) != want:
                row["local_drift"].append(rel)
        meta = github.repo_meta(e["source"])
        head = github.head_sha(e["source"], meta["default_branch"])
        if head != e["sha"]:
            row["upstream_changed"] = github.dir_tree_sha(e["source"], head, e["skill_dir"]) != e["dir_tree_sha"]
            row["head"] = head[:12]
        else:
            row["upstream_changed"] = False
        out.append(row)
    return out

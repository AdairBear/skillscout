"""skillscout command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, digest, discover, install, score, vet
from .config import load_profile


def _vet(profile, scored):
    reports = vet.vet_top(scored, profile.get("vet", "top_k"))
    print(f"[vet] {len(reports)} vetted: " + ", ".join(f"{r['verdict']}" for r in reports), file=sys.stderr)
    return reports


def _digest(profile, scored, reports):
    stats = {"candidates": len(scored), "backend": scored[0]["scores"]["backend"] if scored else "-"}
    text = digest.render(scored, {r["id"]: r for r in reports}, profile.get("digest", "top_n"), stats)
    path = digest.write(text, profile.digest_dir)
    print(f"[digest] {path}", file=sys.stderr)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skillscout", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--profile", type=Path, help="profile.yaml (default ~/.config/skillscout/profile.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover", help="find candidates (cached, rate-limited)")
    sub.add_parser("score", help="score cached candidates")
    sub.add_parser("vet", help="static-scan the top scored candidates")
    sub.add_parser("digest", help="write the shortlist from the last vet run")
    sub.add_parser("weekly", help="discover, score, vet, digest")
    p = sub.add_parser("install", help="install one vetted skill into ~/.claude/skills")
    p.add_argument("id", help="owner/repo/skill")
    p.add_argument("--accept-review", action="store_true", help="allow a REVIEW verdict after reading the report")
    sub.add_parser("check-updates", help="flag upstream changes to installed skills (no update)")
    a = ap.parse_args(argv)

    if a.cmd == "check-updates":
        rows = install.check_updates()
        print(json.dumps(rows, indent=1))
        return 1 if any(r["upstream_changed"] or r["local_drift"] for r in rows) else 0

    profile = load_profile(a.profile)
    if a.cmd == "install":
        print(f"installed to {install.install(a.id, profile.installed_dir, a.accept_review)}")
        return 0
    if a.cmd in ("discover", "weekly"):
        cands = discover.discover(profile)
        print(f"[discover] {len(cands)} candidates", file=sys.stderr)
    if a.cmd == "score":
        score.score(profile, discover.load())
    if a.cmd == "weekly":
        scored = score.score(profile, cands)
        _digest(profile, scored, _vet(profile, scored))
    if a.cmd == "vet":
        _vet(profile, score.load())
    if a.cmd == "digest":
        scored = score.load()
        reports = [r for c in scored if (r := vet.load_report(c["id"]))]
        _digest(profile, scored, reports)
    return 0


if __name__ == "__main__":
    sys.exit(main())

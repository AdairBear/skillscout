"""Score candidates: relevance to the profile, trust signals, and overlap with installed skills."""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import Profile, data_dir
from .discover import parse_frontmatter
from .relevance import similarity_matrix

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Unlicense", "MPL-2.0", "CC0-1.0"}
AUDIT_SCORE = {"pass": 1.0, "warn": 0.3, "fail": 0.0}


def doc_text(c: dict) -> str:
    return f"{c['name']}. {c.get('description', '')}\n{c.get('body', '')[:1500]}"


def installed_skills(root: Path) -> list[dict]:
    out = []
    for md in sorted(root.rglob("SKILL.md")) if root.exists() else []:
        if len(md.relative_to(root).parts) > 4:
            continue
        fm, body = parse_frontmatter(md.read_text(errors="replace"))
        out.append({"name": str(fm.get("name") or md.parent.name), "text": f"{fm.get('description', '')}\n{body[:1500]}"})
    return out


def fetch_audit(skill_id: str) -> str | None:
    """skills.sh partner audits via the official v1 API. Needs SKILLS_SH_TOKEN (Vercel OIDC); off otherwise."""
    token = os.environ.get("SKILLS_SH_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(
        f"https://skills.sh/api/v1/skills/audit/{skill_id}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "skillscout"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            audits = json.loads(resp.read()).get("audits", [])
    except (urllib.error.URLError, ValueError):
        return None
    statuses = {a.get("status") for a in audits}
    return "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass" if statuses else None


def _years_since(iso: str | None) -> float:
    if not iso:
        return 3.0
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - then).days / 365.0


def trust(c: dict, weights: dict) -> tuple[float, dict]:
    parts = {
        "installs": min(1.0, math.log10(1 + (c.get("installs") or 0)) / 5),  # 100k installs -> 1.0
        "stars": min(1.0, math.log10(1 + c.get("stars", 0)) / 4),            # 10k stars -> 1.0
        "official": 1.0 if c.get("official") else 0.0,
        "audit": AUDIT_SCORE.get(c.get("audit"), 0.5),                       # unknown is neutral
        "license": 1.0 if c.get("license") in PERMISSIVE else 0.3 if c.get("license") else 0.0,
        "recency": max(0.0, 1.0 - _years_since(c.get("last_commit"))),
    }
    total = sum(weights.values()) or 1.0
    return sum(parts[k] * weights.get(k, 0) for k in parts) / total, parts


def _minmax(xs: list[float]) -> list[float]:
    lo, hi = min(xs), max(xs)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in xs]


def score(profile: Profile, cands: list[dict]) -> list[dict]:
    if not cands:
        return []
    embed = profile.get("embed")
    docs = [doc_text(c) for c in cands]
    sims, backend = similarity_matrix([i.text for i in profile.interests], docs, embed)
    wmax = max(i.weight for i in profile.interests) or 1.0
    raw_rel, best = [], []
    for d in range(len(cands)):
        per = [(sims[q][d] * profile.interests[q].weight / wmax, profile.interests[q].name)
               for q in range(len(profile.interests))]
        top = max(per)
        raw_rel.append(top[0])
        best.append(top[1])
    rel = _minmax(raw_rel)

    mine = installed_skills(profile.installed_dir)
    if mine:
        osims, _ = similarity_matrix(docs, [m["text"] for m in mine], embed)
    w = profile.get("scoring")
    for idx, c in enumerate(cands):
        c["audit"] = c.get("audit") or fetch_audit(c["id"])
        t, parts = trust(c, profile.get("trust_weights"))
        overlap, twin = 0.0, None
        if mine:
            j = max(range(len(mine)), key=lambda k: osims[idx][k])
            overlap, twin = osims[idx][j], mine[j]["name"]
            if twin.lower() == c["name"].lower():
                overlap = 1.0
        # Only near-duplicates should cost points; loosely related skills are fine.
        penalty = max(0.0, (overlap - 0.75) / 0.25) if backend != "tfidf" else max(0.0, (overlap - 0.4) / 0.6)
        c["scores"] = {
            "relevance": round(rel[idx], 3), "interest": best[idx], "trust": round(t, 3),
            "trust_parts": {k: round(v, 2) for k, v in parts.items()},
            "overlap": round(overlap, 3), "overlaps_with": twin, "backend": backend,
        }
        c["score"] = round(w["relevance"] * rel[idx] + w["trust"] * t - w["overlap_penalty"] * min(1.0, penalty), 4)
    cands.sort(key=lambda c: -c["score"])
    data_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / "scored.json").write_text(json.dumps(cands, indent=1))
    print(f"[score] {len(cands)} candidates scored with {backend}", file=sys.stderr)
    return cands


def load() -> list[dict]:
    return json.loads((data_dir() / "scored.json").read_text())

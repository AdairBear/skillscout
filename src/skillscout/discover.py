"""Discover candidate skills from the skills.sh snapshot, official repos and GitHub code search."""

from __future__ import annotations

import json
import math
import posixpath
import re
import sys

import yaml

from . import github, http
from .config import Profile, data_dir

WEEK = 7 * 86400
BODY_CHARS = 4000


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), m.group(2)


def interest_hits(profile: Profile, text: str) -> list[str]:
    toks = tokens(text)
    hits = []
    for i in profile.interests:
        phrases = [i.name, *i.keywords]
        if any(tokens(p) and tokens(p) <= toks for p in phrases):
            hits.append(i.name)
    return hits


def prefilter_snapshot(profile: Profile, skills: list[dict], budget: int) -> list[dict]:
    """Cheap name-only filter over ~34k skills.sh entries, with a quota per interest for diversity."""
    total_w = sum(i.weight for i in profile.interests) or 1.0
    by_interest: dict[str, list[dict]] = {i.name: [] for i in profile.interests}
    for s in skills:
        for name in interest_hits(profile, f"{s['skillId']} {s['source']}"):
            by_interest[name].append(s)
    chosen: dict[str, dict] = {}
    for i in profile.interests:
        quota = max(1, math.ceil(budget * i.weight / total_w))
        ranked = sorted(by_interest[i.name], key=lambda s: -s.get("installs", 0))
        for s in ranked[:quota]:
            chosen.setdefault(f"{s['source']}/{s['skillId']}", s)
    return list(chosen.values())[:budget]


def load_snapshot(url: str) -> list[dict]:
    try:
        return json.loads(http.get(url, ttl=WEEK))["skills"]
    except (http.FetchError, KeyError, ValueError) as e:
        print(f"[discover] skills.sh snapshot unavailable: {e}", file=sys.stderr)
        return []


def _seed(profile: Profile) -> tuple[dict[str, dict], list[str]]:
    """Return {source: {skillId_or_dir: seed}} and the repo order to visit."""
    disc = profile.get("discovery")
    seeds: dict[str, dict] = {}
    order: list[str] = []

    def add(source: str, key: str, seed: dict) -> None:
        if source not in seeds:
            seeds[source] = {}
            order.append(source)
        seeds[source].setdefault(key, {}).update(seed)

    for src in disc["official_repos"]:
        add(src, "*", {"origin": "official"})
    snap = load_snapshot(disc["skills_sh_snapshot"])
    for s in prefilter_snapshot(profile, snap, disc["max_candidates"] // 2):
        add(s["source"], s["skillId"].lower(), {"origin": "skills.sh", "installs": s.get("installs", 0)})
    installs = {f"{s['source']}/{s['skillId']}".lower(): s.get("installs", 0) for s in snap}
    top = sorted(profile.interests, key=lambda i: -i.weight)[: disc["code_search_queries"]]
    for i in top:
        term = (i.keywords or [i.name])[0]
        try:
            items = github.code_search(f'filename:SKILL.md "{term}"', per_page=10)
        except http.FetchError as e:
            print(f"[discover] code search failed for {term}: {e}", file=sys.stderr)
            items = []
        for it in items:
            d = posixpath.dirname(it["path"])
            key = (posixpath.basename(d) or it["source"].split("/")[1]).lower()
            add(it["source"], key, {"origin": "code-search", "dir": d})
    return {"seeds": seeds, "installs": installs}, order[: disc["max_repos"]]


def _skill_dirs(blobs: list[dict]) -> dict[str, str]:
    """Map lower-cased skill name -> directory, for every SKILL.md in a repo."""
    out = {}
    for b in blobs:
        if posixpath.basename(b["path"]) == "SKILL.md":
            d = posixpath.dirname(b["path"])
            out.setdefault((posixpath.basename(d) or "").lower(), d)
    return out


def build_candidate(source: str, meta: dict, sha: str, blobs: list[dict], skill_dir: str) -> dict | None:
    md_path = posixpath.join(skill_dir, "SKILL.md") if skill_dir else "SKILL.md"
    text = github.raw(source, sha, md_path).decode("utf-8", "replace")
    fm, body = parse_frontmatter(text)
    name = str(fm.get("name") or posixpath.basename(skill_dir) or source.split("/")[1])
    prefix = skill_dir + "/" if skill_dir else ""
    files = [b for b in blobs if b["path"].startswith(prefix)] if skill_dir else [
        b for b in blobs if "/" not in b["path"]]
    return {
        "id": f"{source}/{posixpath.basename(skill_dir) or name}",
        "source": source, "skill_dir": skill_dir, "name": name,
        "description": str(fm.get("description") or "")[:600],
        "body": body[:BODY_CHARS], "sha": sha, "files": files, **meta,
    }


def discover(profile: Profile) -> list[dict]:
    seeded, order = _seed(profile)
    seeds, installs = seeded["seeds"], seeded["installs"]
    official = set(profile.get("discovery", "official_repos"))
    out: dict[str, dict] = {}
    for source in order:
        try:
            meta = github.repo_meta(source)
            if meta["archived"]:
                continue
            sha = github.head_sha(source, meta["default_branch"])
            blobs = github.tree(source, sha)
        except (http.FetchError, KeyError) as e:
            print(f"[discover] skip {source}: {e}", file=sys.stderr)
            continue
        dirs = _skill_dirs(blobs)
        wanted = seeds[source]
        keys = list(dirs) if "*" in wanted else list(wanted)
        for key in keys:
            seed = wanted.get(key, wanted.get("*", {}))
            skill_dir = seed.get("dir", dirs.get(key))
            if skill_dir is None:
                continue
            try:
                c = build_candidate(source, meta, sha, blobs, skill_dir)
                c["last_commit"] = github.last_commit_date(source, skill_dir or "SKILL.md", sha)
            except (http.FetchError, KeyError, IndexError) as e:
                print(f"[discover] skip {source}/{key}: {e}", file=sys.stderr)
                continue
            c["official"] = source in official
            c["origins"] = sorted({seed.get("origin", "official")})
            c["installs"] = installs.get(c["id"].lower(), seed.get("installs"))
            out.setdefault(c["id"], c)
    cands = list(out.values())
    save(cands)
    return cands


def save(cands: list[dict]) -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "candidates.json").write_text(json.dumps(cands, indent=1))


def load() -> list[dict]:
    return json.loads((data_dir() / "candidates.json").read_text())

"""Read-only GitHub helpers. Everything goes through http.get (cached, rate-limited)."""

from __future__ import annotations

import urllib.parse

from . import http

API = "https://api.github.com"
DAY = 86400


def repo_meta(source: str) -> dict:
    r = http.get_json(f"{API}/repos/{source}", ttl=DAY)
    return {
        "stars": r.get("stargazers_count", 0),
        "license": (r.get("license") or {}).get("spdx_id") or None,
        "default_branch": r.get("default_branch", "main"),
        "archived": bool(r.get("archived")),
        "fork": bool(r.get("fork")),
    }


def head_sha(source: str, branch: str) -> str:
    return http.get_json(f"{API}/repos/{source}/commits/{urllib.parse.quote(branch)}", ttl=DAY)["sha"]


def tree(source: str, sha: str) -> list[dict]:
    """All blobs at a commit. Pinned by SHA, so cached forever."""
    t = http.get_json(f"{API}/repos/{source}/git/trees/{sha}?recursive=1", ttl=-1)
    return [
        {"path": e["path"], "sha": e["sha"], "size": e.get("size", 0)}
        for e in t.get("tree", []) if e["type"] == "blob"
    ]


def dir_tree_sha(source: str, sha: str, skill_dir: str) -> str | None:
    """Git tree SHA of a directory: changes whenever any file under it changes."""
    if not skill_dir:
        return sha
    t = http.get_json(f"{API}/repos/{source}/git/trees/{sha}?recursive=1", ttl=-1)
    for e in t.get("tree", []):
        if e["type"] == "tree" and e["path"] == skill_dir:
            return e["sha"]
    return None


def last_commit_date(source: str, path: str, branch: str) -> str | None:
    q = urllib.parse.urlencode({"path": path, "sha": branch, "per_page": 1})
    commits = http.get_json(f"{API}/repos/{source}/commits?{q}", ttl=DAY)
    return commits[0]["commit"]["committer"]["date"] if commits else None


def raw(source: str, sha: str, path: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{source}/{sha}/{urllib.parse.quote(path)}"
    return http.get(url, ttl=-1)


def code_search(query: str, per_page: int = 30) -> list[dict]:
    """GitHub code search (needs a token). Returns [{source, path}]."""
    if not http.github_token():
        return []
    q = urllib.parse.urlencode({"q": query, "per_page": per_page})
    res = http.get_json(f"{API}/search/code?{q}", ttl=7 * DAY, bucket="code-search")
    return [
        {"source": i["repository"]["full_name"], "path": i["path"]}
        for i in res.get("items", []) if not i["repository"].get("fork")
    ]

"""Weekly shortlist as Markdown. Candidate text is untrusted, so it is escaped and quoted."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from .vet import _visible

FRONT_MATTER = """---
from: "night-shift"
to: "Dispatch"
task: "SKILLSCOUT"
status: "needs-thomas"
verified: "{verified}"
unverified: "skill behaviour at runtime (static scan only); skills.sh partner audits unless SKILLS_SH_TOKEN is set"
next_step: "Thomas picks; install with skillscout install <id>"
---
"""


def _clean(text: str, n: int = 220) -> str:
    one = _visible(" ".join((text or "").split()))
    one = one.replace("`", "'").replace("<", "&lt;").replace(">", "&gt;")
    return one[:n] + ("…" if len(one) > n else "")


def _entry(rank: int, c: dict, r: dict) -> list[str]:
    s = c["scores"]
    path = f"/tree/{c['sha']}/{c['skill_dir']}" if c["skill_dir"] else f"/tree/{c['sha']}"
    counts = Counter(f["rule"] for f in r["findings"])
    flags = ", ".join(f"{k}×{v}" for k, v in counts.most_common()) or "none"
    installs = c.get("installs")
    lines = [
        f"### {rank}. {_clean(c['name'], 60)}  (`{c['id']}`)",
        f"- Score {c['score']:.2f}: relevance {s['relevance']:.2f} ({s['interest']}), trust {s['trust']:.2f}"
        + (f", overlaps `{s['overlaps_with']}` {s['overlap']:.2f}" if s.get("overlaps_with") else ""),
        f"- Vet: **{r['verdict']}** (flags: {flags}); licence {r['licence'] or 'none'}; "
        f"{'official' if c.get('official') else 'community'}; "
        f"{installs if installs is not None else '?'} installs; {c.get('stars', 0)} stars; "
        f"last commit {(c.get('last_commit') or '?')[:10]}",
        f"- Pinned: https://github.com/{c['source']}{path}",
        f"- Says (quoted, untrusted): > {_clean(c.get('description', ''))}",
        f"- Install: `skillscout install {c['id']}`",
    ]
    return lines


def render(scored: list[dict], reports: dict[str, dict], top_n: int, stats: dict, today: date | None = None) -> str:
    today = today or date.today()
    picks, failed = [], []
    for c in scored:
        r = reports.get(c["id"])
        if r is None:
            continue
        if r["verdict"] == "FAIL":
            failed.append(c["id"])
        elif len(picks) < top_n:
            picks.append((c, r))
    verified = (f"{stats.get('candidates', 0)} candidates scored ({stats.get('backend', '?')}), "
                f"{len(reports)} statically vetted at pinned SHAs")
    out = [FRONT_MATTER.format(verified=verified), f"# skillscout digest, {today.isoformat()}", "",
           f"Top {len(picks)} skills for this profile. Nothing was installed. "
           "Vet reports live in the local skillscout data dir.", ""]
    for i, (c, r) in enumerate(picks, 1):
        out += _entry(i, c, r) + [""]
    if failed:
        out += ["## Held back (vet FAIL)", ""] + [f"- `{x}`" for x in failed] + [""]
    out.append(f"STATUS: {len(picks)} picks, {len(failed)} held back, 0 installed")
    return "\n".join(out) + "\n"


def write(text: str, digest_dir: Path, today: date | None = None) -> Path:
    today = today or date.today()
    digest_dir.mkdir(parents=True, exist_ok=True)
    path = digest_dir / f"{today.isoformat()}-SKILLSCOUT.md"
    path.write_text(text)
    return path

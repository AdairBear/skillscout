# skillscout

> **WIP, building in public.** v0.1. Expect rough edges; see the [roadmap](ROADMAP.md).

skillscout finds agent skills (`SKILL.md` folders for Claude Code and similar agents) that match *your*
interests, checks how far to trust them, scans them statically for anything hostile, and writes a short
weekly digest. It never installs anything unless you run `skillscout install <id>`, and it **never
executes candidate code**.

```
profile.yaml ─▶ discover ─▶ score ─▶ vet ─▶ digest ─▶ (you pick) ─▶ install <id>
                 skills.sh    local      static     top 5            pinned SHA,
                 official     models     scan only                   hash registry
                 GitHub       only
```

## Pipeline

1. **Profile.** Your interests and weights live in `~/.config/skillscout/profile.yaml`, outside the repo.
   Start from [`profile.example.yaml`](profile.example.yaml).
2. **Discover.** Three sources, all cached and rate-limited:
   - the skills.sh catalogue, read from the MIT-licensed snapshot that
     [mastra-ai/skills-api](https://github.com/mastra-ai/skills-api) publishes. skills.sh's own
     `robots.txt` disallows `/api/` and its v1 API needs a Vercel OIDC token, so skillscout doesn't crawl it.
   - official repos (`anthropics/skills`, `vercel-labs/agent-skills`, `vercel-labs/skills`)
   - GitHub code search for `SKILL.md` matching your top interests (needs `gh auth login` or `GITHUB_TOKEN`)
3. **Score.**
   - *Relevance* from local models only: Ollama embeddings (`nomic-embed-text` by default), falling back
     to TF-IDF. No cloud LLM calls.
   - *Trust* from installs, stars, official source, licence, last commit, and skills.sh partner audits
     (only if you set `SKILLS_SH_TOKEN`).
   - *Overlap*: near-duplicates of skills already in `~/.claude/skills` lose points.
4. **Vet.** A static scan of the top skills at a pinned commit SHA: prompt-injection phrasing, hidden
   Unicode (tag characters, bidi overrides, zero-width), exfiltration asks, network calls,
   exec/eval/subprocess, `curl | sh`, writes outside the skill dir, persistence, committed secrets,
   binaries and licence. Verdicts: `PASS`, `REVIEW` (read the report first) or `FAIL` (held back).
5. **Digest.** The top 5 non-FAIL skills go to `<digest.dir>/<date>-SKILLSCOUT.md` (default `./digest/`).
6. **Install** only on request. `skillscout install <id>` copies exactly the bytes that were vetted,
   refuses `FAIL`, asks for `--accept-review` on `REVIEW`, and records SHA-256 hashes in a registry.
   `skillscout check-updates` flags upstream changes and local drift; it never pulls updates.

## Use

```sh
uv sync
mkdir -p ~/.config/skillscout && cp profile.example.yaml ~/.config/skillscout/profile.yaml
uv run skillscout weekly              # discover → score → vet → digest
uv run skillscout install owner/repo/skill
uv run skillscout check-updates
```

Data lives in `~/.local/share/skillscout` (candidates, vet reports, pinned files, registry) and the HTTP
cache in `~/.cache/skillscout`. Override with `SKILLSCOUT_HOME`, `SKILLSCOUT_CACHE`, `SKILLSCOUT_PROFILE`.

### Weekly job (macOS)

`scripts/install-launchd.sh` renders `launchd/skillscout.weekly.plist.in` into `~/Library/LaunchAgents`
and loads it. It runs `skillscout weekly` on Mondays at 07:00 and logs to `~/Library/Logs/skillscout.log`.

## Limits (be honest)

- A static scan catches known patterns, not intent. `PASS` means "nothing matched", not "safe".
- The skills.sh snapshot can lag the live site by months; install counts are as of that snapshot.
- Rules are pattern-based, so a skill *about* prompt injection may get flagged. That's on purpose:
  a human looks at every FAIL.

## Development

```sh
uv run pytest
scripts/secret-scan.sh   # also runs from .githooks/pre-push
```

Contributions welcome once v0.1 settles. MIT licensed.

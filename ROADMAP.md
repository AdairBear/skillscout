# Roadmap

## v0.1 (now)
- [x] Profile outside the repo, example profile in it
- [x] Discover: skills.sh snapshot, official repos, GitHub code search; cached, rate-limited
- [x] Score: Ollama embeddings or TF-IDF relevance, trust signals, overlap with installed skills
- [x] Vet: static scanner with malicious-fixture tests, pinned SHA, per-skill report
- [x] Weekly digest (top 5), explicit install with hash registry, `check-updates`
- [x] launchd weekly job

## v0.2
- Apple `fm` embeddings as a second local backend
- Context-aware rules: tell "a skill that *explains* prompt injection" from "a skill that *does* it"
- Scan fenced code blocks in SKILL.md with the code rules only, prose with the prose rules only
- Re-vet automatically when `check-updates` flags a change (still no auto-install)
- skills.sh partner audits when a token is available, shown per partner in the digest

## Later
- SARIF output for the vet report
- `skillscout explain <id>`: why it ranked where it did
- Other skill formats (Codex, Cursor rules)

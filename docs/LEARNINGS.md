# Learnings

Append on mistakes, blocked actions, 3+ tries and quirks.

- 2026-10-27: skills.sh robots.txt disallows /api/ and the v1 API needs a Vercel OIDC token, so discovery reads the mastra-ai/skills-api snapshot instead.
- 2026-10-27: first real sweep FAILed three good skills on doc prose (HTTP POST docs, "do not tell the user they need", "never curl|sh"). Rules now need a destination for exfil, skip advice phrasing, and downgrade same-line negated exec/fs hits to REVIEW (never injection/secrets).

#!/bin/sh
# Secret and personal-info scan. Runs before every push (.githooks/pre-push) and in CI.
set -eu
cd "$(git rev-parse --show-toplevel)"
fail=0
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks git --no-banner --redact . || fail=1
  gitleaks dir --no-banner --redact . || fail=1
else
  echo "secret-scan: gitleaks not installed" >&2; fail=1
fi
# No home paths or personal mail in tracked files. Patterns are split so this script doesn't match itself.
home='/Us''ers/|/ho''me/[a-z]'
mail='@gm''ail\.com|@ic''loud\.com'
if git ls-files -z | xargs -0 grep -nE "$home|$mail" -- 2>/dev/null; then
  echo "secret-scan: personal path or email in tracked files" >&2; fail=1
fi
# Commit identities must be noreply.
if git log --format='%ae%n%ce' | grep -v 'users.noreply.github.com$' | grep -q .; then
  echo "secret-scan: non-noreply author/committer email in history" >&2; fail=1
fi
[ "$fail" -eq 0 ] && echo "secret-scan: clean"
exit "$fail"

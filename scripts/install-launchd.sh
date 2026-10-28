#!/bin/sh
# Render the weekly job for this machine and (re)load it as a user LaunchAgent.
set -eu
repo="$(cd "$(dirname "$0")/.." && pwd)"
uv="$(command -v uv)"
label=io.github.skillscout.weekly
plist="$HOME/Library/LaunchAgents/$label.plist"
log="$HOME/Library/Logs/skillscout.log"
path="$(dirname "$uv"):/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
mkdir -p "$(dirname "$plist")"
sed -e "s#@UV@#$uv#g" -e "s#@REPO@#$repo#g" -e "s#@LOG@#$log#g" -e "s#@PATH@#$path#g" \
  "$repo/launchd/skillscout.weekly.plist.in" > "$plist"
plutil -lint "$plist" >/dev/null
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl print "gui/$(id -u)/$label" | grep -E 'state|path' | head -3
echo "loaded $label (Mondays 07:00), log: $log"

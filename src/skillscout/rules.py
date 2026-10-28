"""Static vet rules. Pattern data only; vet.py applies them. Nothing here executes candidate code."""

from __future__ import annotations

import re

# (rule id, category, severity, pattern, what it means)
RULES: list[tuple[str, str, str, re.Pattern, str]] = []


def _r(rid: str, cat: str, sev: str, pattern: str, why: str, flags: int = re.I) -> None:
    RULES.append((rid, cat, sev, re.compile(pattern, flags), why))


# Prompt injection in SKILL.md and other text the agent reads.
_r("PI-IGNORE", "injection", "high",
   r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|system|safety|your|any)\b"
   r"[^.\n]{0,30}\b(instructions?|rules|prompts?|guidelines|guardrails|restrictions)",
   "asks the agent to drop its rules")
_r("PI-SECRECY", "injection", "high",
   # "Don't tell the user they must..." is advice, not concealment, so skip "they/that/you" right after.
   r"\b(do not|don't|never)\s+(tell|inform|mention|reveal|show|alert|notify)\s+(the\s+)?(user|human|operator)\b(?!\s+(they|that|you)\b)",
   "asks the agent to hide actions from the user")
_r("PI-AUTHORITY", "injection", "medium",
   r"\b(pre-?authori[sz]ed|already (been )?approved|admin(istrator)? override|system override|you are now|new system prompt|developer mode)\b",
   "claims authority it does not have")
_r("PI-NOPERMS", "injection", "high",
   r"dangerously-skip-permissions|bypassPermissions|--yolo\b|auto-?approve all",
   "turns off permission prompts")
_r("PI-HTMLCOMMENT", "injection", "high",
   r"<!--(?:(?!-->).){0,400}\b(ignore|instruction|assistant|claude|you must|system prompt)\b(?:(?!-->).){0,400}-->",
   "instructions hidden in an HTML comment", re.I | re.S)
_r("EXFIL-ASK", "exfiltration", "high",
   # Needs a secret AND a destination; "POST /v1/... token" API docs must not match.
   r"\b(send|upload|exfiltrate|forward|transmit|paste|email)\b[^.\n]{0,60}\b(credentials?|secrets?|tokens?|api[ _-]?keys?|passwords?"
   r"|env(ironment)? variables|\.env\b|ssh keys?|cookies|private keys?)\b[^.\n]{0,60}\bto\s+(https?://|[\w.+-]+@|"
   r"(a|an|the|this|our|my)\s+(url|server|webhook|endpoint|email|address|channel|gist|pastebin|discord|telegram))",
   "asks to send secrets somewhere")
_r("SENSITIVE-READ", "exfiltration", "medium",
   r"~/\.ssh|\bid_(rsa|ed25519)\b|\.aws/credentials|\.netrc\b|\bsecurity find-generic-password|/etc/passwd|\.claude/\.credentials",
   "touches credential stores")

# Code behaviour (scripts and fenced code in markdown).
_r("PIPE-SHELL", "exec", "critical", r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b",
   "pipes a download straight into a shell")
_r("RM-RF-ROOT", "exec", "critical", r"\brm\s+-[a-z]*r[a-z]*f?\s+(/(\s|$)|~/?(\s|$)|\$HOME/?(\s|$))",
   "deletes home or root")
_r("EXEC", "exec", "medium",
   r"\b(eval|exec)\s*\(|\bsubprocess\b|\bos\.(system|popen)\b|\bchild_process\b|\bexecSync\b|\bRuntime\.getRuntime\b|\bshell\s*=\s*True",
   "runs commands or dynamic code")
_r("NETWORK", "network", "medium",
   r"\b(curl|wget)\s|\brequests\.(get|post|put)\b|\burllib\.request\b|\bhttp\.client\b|\bfetch\(\s*['\"`]https?:|\baxios\b"
   r"|\bsocket\.(socket|connect)\b|\bInvoke-WebRequest\b|\bnc\s+-",
   "makes network calls")
_r("OBFUSCATION", "exec", "critical", r"base64\s+(-d|--decode)[^\n]*\|\s*(ba|z)?sh|\b(eval|exec)\s*\(\s*(base64\.)?b64decode|\beval\s*\(\s*atob\(",
   "decodes and runs hidden code")
_r("BLOB", "exec", "medium", r"[A-Za-z0-9+/]{240,}={0,2}", "long encoded blob", 0)
_r("WRITE-OUTSIDE", "filesystem", "high",
   r"(>>?|\btee\b|\bcp\b|\bmv\b|\bln\s+-s|write_text|writeFileSync|open\([^)\n]*['\"][wa]['\"])[^\n]{0,80}"
   r"(~/|\$HOME|/etc/|/usr/|/Library/|\.\./|\.bashrc|\.zshrc|\.profile|LaunchAgents|\.claude/settings|\.ssh/)",
   "writes outside the skill directory")
_r("PERSISTENCE", "filesystem", "high", r"\bcrontab\s+-|\blaunchctl\s+(load|bootstrap)|\bsystemctl\s+enable|\bchmod\s+[ug]?\+s\b",
   "installs persistence or setuid")
_r("SUDO", "filesystem", "medium", r"\bsudo\s+\w", "needs root")

# Secrets committed in the skill.
_r("SECRET-AWS", "secret", "high", r"\bAKIA[0-9A-Z]{16}\b", "AWS access key", 0)
_r("SECRET-GITHUB", "secret", "high", r"\b(ghp|gho|ghu|ghs)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}", "GitHub token", 0)
_r("SECRET-OPENAI", "secret", "high", r"\bsk-(proj-|ant-)?[A-Za-z0-9_\-]{32,}", "API secret key", 0)
_r("SECRET-SLACK", "secret", "high", r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "Slack token", 0)
_r("SECRET-PEM", "secret", "high", r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "private key", 0)

HIDDEN = [
    ("UNICODE-TAG", "hidden-text", "critical", re.compile("[\U000E0000-\U000E007F]"), "invisible Unicode tag characters"),
    ("UNICODE-BIDI", "hidden-text", "high", re.compile("[‪-‮⁦-⁩]"), "bidirectional override characters"),
    ("UNICODE-ZW", "hidden-text", "medium", re.compile("[​-‍⁠᠎]|(?<!^)﻿"), "zero-width characters"),
]

BINARY_EXT = {".exe", ".dll", ".so", ".dylib", ".bin", ".jar", ".class", ".pyc", ".node", ".wasm", ".app", ".dmg", ".pkg"}
# These categories mean "do not install" even at high severity.
FAIL_CATEGORIES = {"injection", "exfiltration", "hidden-text", "secret"}

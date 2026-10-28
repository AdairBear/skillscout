"""Paths and profile loading. The real profile lives outside the repo (~/.config/skillscout/profile.yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULTS = {
    "scoring": {"relevance": 0.6, "trust": 0.4, "overlap_penalty": 0.3},
    "trust_weights": {
        "installs": 0.25, "stars": 0.15, "official": 0.2,
        "audit": 0.15, "license": 0.1, "recency": 0.15,
    },
    "discovery": {
        "official_repos": ["anthropics/skills", "vercel-labs/agent-skills", "vercel-labs/skills"],
        "max_candidates": 80,
        "max_repos": 50,
        "code_search_queries": 6,
        "skills_sh_snapshot": (
            "https://raw.githubusercontent.com/mastra-ai/skills-api/main/src/registry/scraped-skills.json"
        ),
    },
    "embed": {"backend": "ollama", "model": "nomic-embed-text", "url": "http://127.0.0.1:11434"},
    "vet": {"top_k": 15},
    "digest": {"dir": "./digest", "top_n": 5},
    "installed_skills_dir": "~/.claude/skills",
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def profile_path() -> Path:
    env = os.environ.get("SKILLSCOUT_PROFILE")
    if env:
        return Path(env).expanduser()
    return Path("~/.config/skillscout/profile.yaml").expanduser()


def data_dir() -> Path:
    return Path(os.environ.get("SKILLSCOUT_HOME", "~/.local/share/skillscout")).expanduser()


def cache_dir() -> Path:
    return Path(os.environ.get("SKILLSCOUT_CACHE", "~/.cache/skillscout")).expanduser()


@dataclass
class Interest:
    name: str
    weight: float
    keywords: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.name}: " + ", ".join(self.keywords)


@dataclass
class Profile:
    interests: list[Interest]
    settings: dict

    def get(self, *keys):
        node = self.settings
        for k in keys:
            node = node[k]
        return node

    @property
    def digest_dir(self) -> Path:
        return Path(os.path.expandvars(self.get("digest", "dir"))).expanduser()

    @property
    def installed_dir(self) -> Path:
        return Path(self.get("installed_skills_dir")).expanduser()


def load_profile(path: Path | None = None) -> Profile:
    path = path or profile_path()
    if not path.exists():
        raise SystemExit(f"No profile at {path}. Copy profile.example.yaml there and edit it.")
    raw = yaml.safe_load(path.read_text()) or {}
    interests = [
        Interest(str(i["name"]), float(i.get("weight", 1.0)), [str(k) for k in i.get("keywords", [])])
        for i in raw.get("interests", [])
    ]
    if not interests:
        raise SystemExit(f"Profile {path} has no interests.")
    settings = _merge(DEFAULTS, {k: v for k, v in raw.items() if k != "interests"})
    return Profile(interests, settings)

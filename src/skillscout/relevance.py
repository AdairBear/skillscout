"""Text similarity on local models only: Ollama embeddings, falling back to TF-IDF. No cloud LLM calls."""

from __future__ import annotations

import json
import math
import re
import sys
import urllib.error
import urllib.request
from collections import Counter


def _tok(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    tfs = [Counter(_tok(d)) for d in docs]
    df = Counter(t for tf in tfs for t in tf)
    n = len(docs)
    vecs = []
    for tf in tfs:
        v = {t: (1 + math.log(c)) * math.log((1 + n) / (1 + df[t])) + 1e-9 for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def _cos_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def ollama_embed(texts: list[str], model: str, url: str) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), 32):
        body = json.dumps({"model": model, "input": texts[i:i + 32]}).encode()
        req = urllib.request.Request(f"{url}/api/embed", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out.extend(json.loads(resp.read())["embeddings"])
    return out


def similarity_matrix(queries: list[str], docs: list[str], embed: dict) -> tuple[list[list[float]], str]:
    """sims[q][d] in roughly [0, 1], plus the backend actually used."""
    if embed.get("backend") == "ollama":
        try:
            # nomic-style task prefixes; harmless for models that ignore them.
            q = ollama_embed([f"search_query: {t}" for t in queries], embed["model"], embed["url"])
            d = ollama_embed([f"search_document: {t}" for t in docs], embed["model"], embed["url"])
            return [[_cos(a, b) for b in d] for a in q], f"ollama:{embed['model']}"
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            print(f"[relevance] Ollama unavailable ({e}); using TF-IDF", file=sys.stderr)
    vecs = tfidf_vectors(queries + docs)
    qv, dv = vecs[: len(queries)], vecs[len(queries):]
    return [[_cos_sparse(a, b) for b in dv] for a in qv], "tfidf"

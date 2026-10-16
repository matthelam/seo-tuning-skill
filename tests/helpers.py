"""Fake seo-jev results shaped like result@1, so the tests never need a deployment or a key."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "seo-tuning" / "scripts"))

TERMS = [f"term {i}" for i in range(10)]


def result(meta=3.0, page=7.0, ratings=None, runs=3, title="Old title", description="Old description"):
    r = ratings or {t: (0.8 if i < 6 else 0.2) for i, t in enumerate(TERMS)}

    def s(score):
        return {"score": score, "sd": 0.05, "termSum": sum(r.values()), "intentFit": 0.7,
                "intentProbabilities": {}, "ratings": r, "pointsAvailable": []}

    return {"schema": "seo-jev-analyzer/result@1", "page": "https://example.com/guide", "scoredAt": "2026-01-01T00:00:00Z",
            "model": "jev-test", "questionVersion": "q1", "fingerprint": "f", "inputs": {}, "runs": runs, "noiseFloor": 0.194,
            "text": {"source": "url", "bodyChars": 100, "textHash": "h", "warnings": [],
                     "meta": {"title": f"{title} | Example", "description": description, "ogTitle": title,
                              "ogDescription": description, "jsonLd": ["Article", title, description]}},
            "scores": {"meta": s(meta), "page": s(page)}}


def trial(meta_verdict="up", page_verdict="level", meta_delta=0.5, comparable=True):
    return {"current": result(), "revised": result(meta=3.5),
            "comparison": {"comparable": comparable, "noiseFloor": 0.194, "threshold": 0.158, "scores": {
                "meta": {"before": 3.0, "after": 3.0 + meta_delta, "delta": meta_delta, "verdict": meta_verdict},
                "page": {"before": 7.0, "after": 7.0, "delta": 0.0, "verdict": page_verdict}}}}

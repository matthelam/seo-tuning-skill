"""Pure functions for the tuning loop: no network, no files. Everything here is unit-tested.

Result objects are seo-jev-analyzer `result@1` JSON (from score_page) and test_revision replies.
"""
import math
import re
from urllib.parse import urlparse

COVERED = 0.5  # a whole-page term rating at or above this counts as covered
MAX_TERMS = 100


def slug_of(path):
    """A file-safe slug for a page path: '/blog/My Post/' -> 'My_Post', '/' -> 'home'."""
    last = path.split("?")[0].strip("/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", last.replace("%20", " ")) or "home"


def threshold(noise_floor, runs, baseline_runs):
    """A change larger than this is up or down; inside it, level."""
    return noise_floor * math.sqrt(1 / runs + 1 / baseline_runs)


def score(result, kind):
    return (((result or {}).get("scores") or {}).get(kind) or {}).get("score")


def fidelity(result):
    """North star: how much of the whole page's score the metadata alone gets across."""
    m, p = score(result, "meta"), score(result, "page")
    return m / p if m is not None and p else None


def ratings(result, kind):
    return (((result or {}).get("scores") or {}).get(kind) or {}).get("ratings") or {}


def covered(result, terms, at=COVERED):
    r = ratings(result, "page")
    return [t for t in terms if r.get(t, 0) >= at]


def uncovered(result, terms, at=COVERED):
    r = ratings(result, "page")
    return [t for t in terms if r.get(t, 0) < at]


def terms_for(expected, vocabulary):
    """The terms list for a call: the page's 10 expected first, then the site vocabulary, max 100."""
    return list(dict.fromkeys(list(expected) + list(vocabulary)))[:MAX_TERMS]


def summary_line(slug, result, expected):
    if not result or "error" in result:
        return f"{slug}: ERROR {(result or {}).get('error', 'no result')[:200]}"
    m, p = result["scores"]["meta"], result["scores"]["page"]
    f = fidelity(result)
    return (f"{slug}: meta {m['score']:.2f} (fit {m['intentFit']:.2f}) | page {p['score']:.2f} "
            f"(fit {p['intentFit']:.2f}) | fidelity {f:.0%} | covered {len(covered(result, expected))}/{len(expected)}"
            if f is not None else f"{slug}: meta {m['score']:.2f} | page {p['score']:.2f}")


# --- keyword research -------------------------------------------------------------------------

def domain_of(source):
    """'https://www.example.com/a b' or 'example.com/a notes' -> 'example.com'."""
    s = str(source).strip().split()[0] if str(source).strip() else ""
    host = urlparse(s if "://" in s else "//" + s).hostname or ""
    return host[4:] if host.startswith("www.") else host


def validate_keywords(doc, intent, need=10, min_sources=2):
    """Problems with one page's keyword research file; an empty list means it passes."""
    problems = []
    if (doc.get("intent") or "").strip() != (intent or "").strip():
        problems.append("intent in the research file does not match the page's intent")
    sel = doc.get("selected") or []
    if len(sel) != need:
        problems.append(f"{len(sel)} keywords selected, need exactly {need}")
    seen = set()
    for k in sel:
        term = (k.get("term") or "").strip()
        if not term:
            problems.append("a keyword has no term")
            continue
        if term.lower() in seen:
            problems.append(f"duplicate keyword: {term}")
        seen.add(term.lower())
        if len(term) > 120:
            problems.append(f"keyword longer than 120 characters: {term[:40]}...")
        domains = {domain_of(s) for s in k.get("sources") or []} - {""}
        if len(domains) < min_sources:
            problems.append(f"'{term}': {len(domains)} independent source(s), need {min_sources}")
    return problems


def keyword_terms(doc):
    return [k["term"].strip() for k in doc.get("selected") or []]


# --- revisions and trials ---------------------------------------------------------------------

def meta_revision(meta, title, description):
    """A revision that swaps the live title and description for a candidate's, everywhere they
    appear: <title> (keeping any site suffix), Open Graph, and JSON-LD text."""
    old_t = meta.get("ogTitle") or meta["title"]
    old_d = meta.get("description") or meta.get("ogDescription") or ""

    def sub(s):
        if not isinstance(s, str):
            return s
        if old_t:
            s = s.replace(old_t, title)
        if old_d:
            s = s.replace(old_d, description)
        return s

    full = meta["title"].replace(old_t, title) if old_t and old_t in meta["title"] else title
    return {"title": full, "description": description, "ogTitle": title, "ogDescription": description,
            "jsonLd": [sub(x) for x in meta.get("jsonLd") or []]}


def is_winner(trial):
    """A trial wins when it is comparable, metadata goes up beyond the noise threshold and the
    whole page does not go down. Verdicts come from the server, which applies the threshold."""
    if not trial or "error" in trial:
        return False
    cmp = trial.get("comparison") or {}
    if cmp.get("comparable") is False:
        return False
    s = cmp.get("scores") or {}
    meta, page = (s.get("meta") or {}).get("verdict"), (s.get("page") or {}).get("verdict")
    if meta is None:  # body-only trial: judged on the whole page
        return page == "up"
    return meta == "up" and page != "down"


def best_winner(trials):
    """[(candidate, result)] -> the winner with the largest metadata gain, or None."""
    wins = [(c, r) for c, r in trials if is_winner(r)]
    if not wins:
        return None

    def gain(cr):
        s = cr[1]["comparison"]["scores"]
        return (s.get("meta") or s["page"])["delta"]

    return max(wins, key=gain)


def trial_summary(result):
    """What the report keeps of a trial: the comparison, not the full revised result."""
    if "error" in result:
        return {"error": result["error"]}
    rev = (result.get("revised") or {}).get("text") or {}
    return {"comparison": result.get("comparison"), "changed": result.get("changed"), "revisedMeta": rev.get("meta")}


def line_for_trial(name, result):
    if "error" in result:
        return f"   {name[:58]:58} ERROR {result['error'][:160]}"
    s = " | ".join(f"{k} {v['before']:.2f}->{v['after']:.2f} ({v['delta']:+.2f} {v['verdict']})"
                   for k, v in (result.get("comparison") or {}).get("scores", {}).items())
    return f"   {name[:58]:58} {s}{'  WIN' if is_winner(result) else ''}"


# --- state and stopping -----------------------------------------------------------------------

def pass_id(n):
    return f"pass-{int(n):02d}"


def get_pass(page, n, kind=None):
    """The page's record for pass n, created on first use."""
    pid = pass_id(n)
    for p in page["passes"]:
        if p["id"] == pid:
            return p
    p = {"id": pid, "label": "Baseline" if int(n) == 0 else f"Pass {int(n)}",
         "kind": kind or ("baseline" if int(n) == 0 else "metadata"),
         "notes": [], "decisions": [], "trials": [], "live": None, "pr": None}
    page["passes"].append(p)
    page["passes"].sort(key=lambda x: x["id"])
    return p


def latest_live(page):
    for p in reversed(page["passes"]):
        if p.get("live"):
            return p["live"]
    return None


def page_done(page, results, patience=2, noise_floor=0.194):
    """A page leaves the loop when its metadata is within the noise band of its whole-page score,
    or its last `patience` passes with trials produced no winner. Returns a reason or None.
    `results` maps a stored file name to its loaded result."""
    live = results.get(latest_live(page) or "")
    if live and "error" not in live:
        m, p = score(live, "meta"), score(live, "page")
        runs = live.get("runs", 1)
        if m is not None and p is not None and p - m <= threshold(noise_floor, runs, runs):
            return "metadata within noise of the whole-page score"
    tried = [p for p in page["passes"] if p.get("trials")]
    if len(tried) >= patience and not any(t.get("winner") for p in tried[-patience:] for t in p["trials"]):
        return f"no winner in the last {patience} passes"
    return None


def stop_reason(state, results, patience=2):
    passes = max((int(p["id"][5:]) for pg in state["pages"] for p in pg["passes"]), default=0)
    if passes >= state.get("maxPasses", 20):
        return f"reached {state.get('maxPasses', 20)} passes"
    active = [pg for pg in state["pages"] if pg.get("included", True)]
    if active and all(page_done(pg, results, patience) for pg in active):
        return "no page has a change that beats the noise floor"
    return None

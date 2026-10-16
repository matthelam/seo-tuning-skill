"""SEO tuning loop driver. Scripts do every seo-jev call and every comparison; the agent decides.

Every command takes --work DIR (default ./seo-tuning), the workspace for one site:
  profile.json                 seo-jev profile@1: domain, vocabulary, boilerplate, pages (intent + expected)
  keywords/<slug>.json         keyword research per page (see references/keyword-research.md)
  state.json                   passes, decisions, backlog
  runs/<slug>/live-NN.json     live scores; trial-NN-<id>.json for test_revision trials
  report/                      the published report (report.html, calc.js, data/)

Commands:
  init --domain D [--sitemap URL] [--path-filter P]   list pages from the sitemap into profile.json
  boilerplate [--sample 12]                          store shared banner/footer lines in the profile
  keywords [--apply]                                 validate keyword research; --apply writes it to the profile
  live --pass N [--runs 3] [--slug S ...]            score live pages; pass 0 is the baseline
  trials --pass N --candidates FILE [--runs 3]       test_revision each candidate against the live page
  record --pass N --slug S --json FILE|-             add notes, decisions or a PR link to a pass
  backlog --term T --why W [--slug S]                add an uncovered keyword to the content backlog
  report [--title T] [--status-text S]               rebuild report/ from state and results
  status                                             one line per page, and whether to stop
"""
import argparse
import datetime
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import tunelib as T

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "report"


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def rj(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def wj(path, data, indent=1):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")


class Work:
    def __init__(self, root):
        self.root = Path(root)

    profile = property(lambda s: rj(s.root / "profile.json"))
    state = property(lambda s: rj(s.root / "state.json"))

    def save_profile(self, p):
        wj(self.root / "profile.json", p)

    def save_state(self, s):
        wj(self.root / "state.json", s)

    def result(self, rel):
        return rj(self.root / rel) if rel else None

    def pages(self, slugs=None, prof=None):
        """Included pages; pass `prof` when you will edit and save the same profile object."""
        prof = prof or self.profile
        out = [pg for pg in prof["pages"] if pg.get("included", True)]
        return [pg for pg in out if not slugs or T.slug_of(pg["path"]) in slugs]

    def state_page(self, state, pg):
        slug = T.slug_of(pg["path"])
        for sp in state["pages"]:
            if sp["slug"] == slug:
                return sp
        sp = {"slug": slug, "path": pg["path"], "url": pg["url"], "intent": pg["intent"], "passes": []}
        state["pages"].append(sp)
        return sp

    def results(self, state):
        files = [p["live"] for sp in state["pages"] for p in sp["passes"] if p.get("live")]
        return {f: self.result(f) for f in files}


def jev():
    import jevclient  # imported late so offline commands never need the environment

    return jevclient.call


def parallel(fn, items, workers=4):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


# --- commands ---------------------------------------------------------------------------------

def cmd_init(w, a):
    if (w.root / "profile.json").exists():
        sys.exit(f"{w.root / 'profile.json'} exists; edit it instead of re-running init.")
    args = {"domain": a.domain}
    if a.sitemap:
        args["sitemapUrl"] = a.sitemap
    if a.path_filter:
        args["pathFilter"] = a.path_filter
    res = jev()("discover_pages", args)
    if "error" in res:
        sys.exit("discover_pages failed: " + res["error"])
    urls = res.get("urls") or [p.get("url") for p in res.get("pages", [])]
    from urllib.parse import urlparse

    pages = [{"url": u, "path": urlparse(u).path or "/", "intent": "", "expected": [], "included": True}
             for u in urls if u]
    w.save_profile({"schema": "seo-jev-analyzer/profile@1", "name": a.name or a.domain, "domain": a.domain,
                    "sitemapUrl": a.sitemap or "", "pathFilter": a.path_filter or "", "terms": [],
                    "boilerplate": [], "pages": pages})
    w.save_state({"schema": "seo-tuning-state@1", "site": a.domain, "title": a.name or a.domain,
                  "maxPasses": 20, "status": "setup", "statusText": "Intents and keywords not set yet",
                  "backlog": [], "pages": []})
    (w.root / "keywords").mkdir(exist_ok=True)
    print(f"{len(pages)} pages from the sitemap -> {w.root / 'profile.json'}")
    print("Next: write one intent per page (or set included: false), then research keywords.")


def cmd_boilerplate(w, a):
    prof = w.profile
    urls = [pg["url"] for pg in w.pages(prof=prof)][: a.sample]
    res = jev()("find_boilerplate", {"urls": urls, "share": a.share})
    if "error" in res:
        sys.exit("find_boilerplate failed: " + res["error"])
    prof["boilerplate"] = res.get("lines") or res.get("boilerplate") or []
    w.save_profile(prof)
    print(len(prof["boilerplate"]), "boilerplate lines stored")


def cmd_keywords(w, a):
    prof, bad = w.profile, 0
    vocab = list(prof.get("terms") or [])
    for pg in w.pages(prof=prof):
        slug = T.slug_of(pg["path"])
        doc = rj(w.root / "keywords" / f"{slug}.json")
        if not pg.get("intent"):
            print(f"{slug}: no intent yet"); bad += 1; continue
        if doc is None:
            print(f"{slug}: no keywords/{slug}.json"); bad += 1; continue
        problems = T.validate_keywords(doc, pg["intent"])
        if problems:
            bad += 1
            print(f"{slug}: " + "; ".join(problems))
            continue
        print(f"{slug}: ok")
        if a.apply:
            pg["expected"] = T.keyword_terms(doc)
            vocab += pg["expected"]
    if a.apply:
        prof["terms"] = list(dict.fromkeys(vocab))[: T.MAX_TERMS]
        w.save_profile(prof)
        print(f"applied; vocabulary {len(prof['terms'])} terms")
    return 1 if bad else 0


def cmd_live(w, a):
    prof, state = w.profile, w.state
    pages = [pg for pg in w.pages(a.slug, prof) if len(pg.get("expected") or []) == 10 and pg.get("intent")]
    if not pages:
        sys.exit("No page has an intent and 10 expected terms; run `keywords --apply` first.")
    call = jev()

    def one(pg):
        r = call("score_page", {"page": pg["url"], "intent": pg["intent"], "expected": pg["expected"],
                                "terms": T.terms_for(pg["expected"], prof["terms"]), "runs": a.runs, "profile": prof})
        rel = f"runs/{T.slug_of(pg['path'])}/live-{int(a.pass_n):02d}.json"
        wj(w.root / rel, r, indent=None)
        return pg, rel, r

    for pg, rel, r in parallel(one, pages, a.workers):
        sp = w.state_page(state, pg)
        p = T.get_pass(sp, a.pass_n)
        p["at"] = now()
        if "error" not in r:
            p["live"] = rel
            meta = r["text"]["meta"]
            sp.setdefault("title", meta.get("ogTitle") or meta.get("title"))
        else:
            p["notes"].append("Live scoring failed: " + r["error"][:200])
        print(T.summary_line(sp["slug"], r, pg["expected"]))
    if state.get("status") == "setup":
        state["status"] = "running"
    w.save_state(state)


def cmd_trials(w, a):
    prof, state = w.profile, w.state
    cands = rj(a.candidates)
    by_slug = {T.slug_of(pg["path"]): pg for pg in w.pages(prof=prof)}
    call = jev()
    jobs = []
    for c in cands:
        pg = by_slug.get(c["slug"])
        if pg is None:
            print(f"{c['slug']}: not an included page, skipped"); continue
        sp = w.state_page(state, pg)
        base_rel = T.latest_live(sp)
        if not base_rel:
            print(f"{c['slug']}: no live score yet, run `live` first"); continue
        jobs.append((c, pg, base_rel))

    def one(job):
        c, pg, base_rel = job
        base = w.result(base_rel)
        rev = c.get("revision") or T.meta_revision(base["text"]["meta"], c["title"], c["description"])
        r = call("test_revision", {"page": pg["url"], "intent": pg["intent"], "expected": pg["expected"],
                                   "terms": T.terms_for(pg["expected"], prof["terms"]), "runs": a.runs,
                                   "profile": prof, "baseline": base, "revision": rev})
        rel = f"runs/{c['slug']}/trial-{int(a.pass_n):02d}-{c['id']}.json"
        wj(w.root / rel, r, indent=None)
        return c, r, rel

    done = parallel(one, jobs, a.workers)
    for slug in dict.fromkeys(c["slug"] for c, _, _ in done):
        sp = w.state_page(state, by_slug[slug])
        p = T.get_pass(sp, a.pass_n, kind="content" if any("revision" in c for c, _, _ in done if c["slug"] == slug) else None)
        p["at"] = now()
        mine = [(c, r, rel) for c, r, rel in done if c["slug"] == slug]
        best = T.best_winner([(c, r) for c, r, _ in mine])
        print(f"{slug}:")
        for c, r, rel in mine:
            label = c["id"] + (": " + c["title"] if c.get("title") else "")
            p["trials"].append({"id": c["id"], "label": label, "file": rel, "winner": best is not None and best[0] is c})
            print(T.line_for_trial(label, r))
        print(f"   -> {'winner ' + best[0]['id'] if best else 'no winner: keep the live page'}")
    w.save_state(state)


def cmd_record(w, a):
    state = w.state
    pg = next((pg for pg in w.pages() if T.slug_of(pg["path"]) == a.slug), None)
    if pg is None:
        sys.exit(f"{a.slug}: not an included page")
    data = json.loads(sys.stdin.read() if a.json == "-" else Path(a.json).read_text(encoding="utf-8"))
    p = T.get_pass(w.state_page(state, pg), a.pass_n)
    p["notes"] += data.get("notes", [])
    p["decisions"] += data.get("decisions", [])
    for k in ("pr", "kind", "label"):
        if data.get(k):
            p[k] = data[k]
    w.save_state(state)
    print(f"{a.slug} {p['id']}: {len(p['notes'])} notes, {len(p['decisions'])} decisions")


def cmd_backlog(w, a):
    state = w.state
    item = {"term": a.term, "why": a.why}
    if a.slug:
        sp = next((sp for sp in state["pages"] if sp["slug"] == a.slug), None)
        if sp is None:
            sys.exit(f"{a.slug}: no such page in state")
        sp.setdefault("backlog", []).append(item)
    else:
        state["backlog"].append(item)
    w.save_state(state)
    print("backlog:", a.term)


def cmd_report(w, a):
    state, out = w.state, w.root / "report"
    if a.title:
        state["title"] = a.title
    if a.status_text:
        state["statusText"] = a.status_text
    for f in ("report.html", "calc.js"):
        (out / "data").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE / f, out / f)
    latest, pages = None, []
    for sp in state["pages"]:
        refs = []
        for p in sp["passes"]:
            live = w.result(p.get("live"))
            if live and "error" not in live:
                latest = live
            body = {k: v for k, v in p.items() if k not in ("live", "trials")}
            body["live"] = live
            body["trials"] = [{"label": t["label"] + (" (winner)" if t.get("winner") else ""),
                               "result": T.trial_summary(w.result(t["file"]) or {"error": "missing file"})}
                              for t in p.get("trials", [])]
            wj(out / "data" / sp["slug"] / f"{p['id']}.json", body, indent=None)
            refs.append({"id": p["id"], "label": p["label"], "file": f"data/{sp['slug']}/{p['id']}.json"})
        kw = rj(w.root / "keywords" / f"{sp['slug']}.json") or {}
        keywords = [{"term": k["term"], "sources": len({T.domain_of(s) for s in k.get("sources", [])} - {""}),
                     "sourceList": k.get("sources", [])} for k in kw.get("selected", [])]
        pages.append({**{k: v for k, v in sp.items() if k != "passes"}, "keywords": keywords, "passes": refs})
    wj(out / "data" / "index.json", {
        "schema": "seo-tuning-report@2", "site": state["site"], "scope": "series" if len(pages) > 1 else "page",
        "title": state["title"], "maxPasses": state.get("maxPasses", 20),
        "stopRule": f"Stop at {state.get('maxPasses', 20)} passes, or when no change beats the noise floor.",
        "status": state.get("status", "running"), "statusText": state.get("statusText", ""), "updated": now(),
        "backlog": state.get("backlog", []), "pages": pages})
    wj(out / "data" / "method.json", {k: (latest or {}).get(k) for k in ("model", "questionVersion", "noiseFloor")})
    w.save_state(state)
    print(f"report: {len(pages)} pages, {sum(len(p['passes']) for p in pages)} pass files -> {out}")


def cmd_status(w, a):
    state = w.state
    results = w.results(state)
    exp = {T.slug_of(pg["path"]): pg.get("expected", []) for pg in w.profile["pages"]}
    for sp in state["pages"]:
        live = results.get(T.latest_live(sp) or "")
        done = T.page_done(sp, results, a.patience)
        print(T.summary_line(sp["slug"], live, exp.get(sp["slug"], [])) + f" | passes {len(sp['passes']) - 1}"
              + (f" | DONE: {done}" if done else ""))
    reason = T.stop_reason(state, results, a.patience)
    print("STOP: " + reason if reason else "CONTINUE")


def main(argv=None):
    ap = argparse.ArgumentParser(description="SEO tuning loop driver", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--work", default="seo-tuning")
    ap.add_argument("--workers", type=int, default=4)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--domain", required=True); s.add_argument("--sitemap")
    s.add_argument("--path-filter"); s.add_argument("--name")
    s = sub.add_parser("boilerplate"); s.add_argument("--sample", type=int, default=12)
    s.add_argument("--share", type=float, default=0.8)
    s = sub.add_parser("keywords"); s.add_argument("--apply", action="store_true")
    s = sub.add_parser("live"); s.add_argument("--pass", dest="pass_n", type=int, required=True)
    s.add_argument("--runs", type=int, default=3); s.add_argument("--slug", nargs="*")
    s = sub.add_parser("trials"); s.add_argument("--pass", dest="pass_n", type=int, required=True)
    s.add_argument("--candidates", required=True); s.add_argument("--runs", type=int, default=3)
    s = sub.add_parser("record"); s.add_argument("--pass", dest="pass_n", type=int, required=True)
    s.add_argument("--slug", required=True); s.add_argument("--json", required=True)
    s = sub.add_parser("backlog"); s.add_argument("--term", required=True); s.add_argument("--why", required=True)
    s.add_argument("--slug")
    s = sub.add_parser("report"); s.add_argument("--title"); s.add_argument("--status-text")
    s = sub.add_parser("status"); s.add_argument("--patience", type=int, default=2)
    a = ap.parse_args(argv)
    w = Work(a.work)
    if a.cmd != "init" and not (w.root / "profile.json").exists():
        sys.exit(f"No workspace at {w.root}; run `init` first or pass --work.")
    return globals()["cmd_" + a.cmd](w, a) or 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

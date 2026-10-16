# Workspace and file formats

One workspace per site, passed to every command as `--work <dir>`.

```
<work>/
  profile.json               seo-jev profile: pages, intents, expected terms, vocabulary
  keywords/<slug>.json       keyword research per page (keyword-research.md)
  state.json                 passes, decisions, backlog: the loop's memory
  runs/<slug>/live-NN.json   score_page result for the live page after pass NN (00 = baseline)
  runs/<slug>/trial-NN-<id>.json   test_revision result for one candidate
  report/                    report.html, calc.js, data/ (rebuilt by `tune.py report`)
```

`<slug>` is the last part of the page path, made file-safe (`/` is `home`).

## profile.json (`seo-jev-analyzer/profile@1`)

The same format the seo-jev-analyzer web app exports, so a profile can move between the two.

```json
{
  "schema": "seo-jev-analyzer/profile@1",
  "name": "example.com", "domain": "example.com", "sitemapUrl": "", "pathFilter": "",
  "terms": ["up to 100 terms: every page's expected terms, the site vocabulary"],
  "boilerplate": ["lines repeated on most pages, removed before scoring"],
  "pages": [
    {"url": "https://example.com/guide", "path": "/guide", "intent": "How do I ...?",
     "expected": ["10 researched keywords"], "included": true}
  ]
}
```

## state.json (`seo-tuning-state@1`)

Written by the scripts; change it only through `record` and `backlog`.

```json
{
  "schema": "seo-tuning-state@1", "site": "example.com", "title": "example.com tuning",
  "maxPasses": 20, "status": "running", "statusText": "Pass 2 live",
  "backlog": [{"term": "...", "why": "..."}],
  "pages": [{
    "slug": "guide", "path": "/guide", "url": "https://example.com/guide", "intent": "...",
    "title": "live title", "backlog": [],
    "passes": [{
      "id": "pass-01", "label": "Pass 1", "kind": "metadata", "at": "2026-01-01 10:00",
      "live": "runs/guide/live-01.json",
      "trials": [{"id": "c1", "label": "c1: Title", "file": "runs/guide/trial-01-c1.json", "winner": true}],
      "notes": ["..."],
      "decisions": [{"kind": "metadata", "status": "kept", "title": "Winner c1",
                     "detail": "optional", "diff": [["old", "new"]]}],
      "pr": "https://link-to-the-change"
    }]
  }]
}
```

Optional page fields for the report: `short` (button label) and `statusText`.

## Candidates file (input to `trials`)

```json
[
  {"slug": "guide", "id": "c1", "title": "New title", "description": "New description"},
  {"slug": "guide", "id": "b1", "revision": {"body": "Full revised body text, one paragraph per line"}}
]
```

A title and description are swapped into the live `<title>`, Open Graph and JSON-LD text, the way
the site would render them. `revision` sends any `test_revision` fields as given (`title`,
`description`, `ogTitle`, `ogDescription`, `jsonLd`, `body`); use it for content edits.

## Report data (`seo-tuning-report@2`)

`data/index.json` lists pages with their intent, keywords (term, source count, sources), backlog
and pass files. `data/<slug>/pass-NN.json` holds the pass record with the full live result and a
summary of each trial (its comparison only). `data/method.json` holds the Jev model, question
version and noise floor of the latest live result. `report.html` and `calc.js` read these and
nothing else.

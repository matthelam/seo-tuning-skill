---
name: seo-tuning
description: Tune a website's pages for search and answer-engine relevance with measured, repeatable passes, using two MCP tools - seo-jev-analyzer (does each page answer its search intent; metadata vs whole-page scores, test_revision, noise floor) and is-agentic (technical readiness for crawlers and agents). Use when someone wants to improve SEO or AEO for a site or a set of pages, tune titles and meta descriptions, find out whether a page matches what people search for, research keywords for a page, test metadata before publishing, or run or continue an "SEO tuning loop" or "SEO pass". Not for writing new pages from scratch, link building, or paid search.
---

# SEO tuning

Tune each page so its title, description and structured data say what the page actually answers,
measured against a search intent and ten researched keywords. Scripts do the scoring and the
comparisons; you make the decisions. Every number in the report comes from a tool result.

## The idea in three lines

- **The page is the ceiling.** seo-jev scores the metadata alone and the whole page. The whole-page
  score is what the content supports; metadata cannot honestly claim more.
- **North star: fidelity** = metadata score / whole-page score, plus **keyword coverage** (how many
  of the ten keywords the page covers, rating 0.5 or more). Aim for fidelity close to 100%.
- **Keywords the page does not cover go to a content backlog**, never into the metadata.

## Before you start

Check, and stop with a clear message if any is missing (setup is in the repository README):

1. `python <skill>/scripts/jevclient.py check` prints `ok`. It needs `SEO_JEV_MCP_URL` and
   `SEO_JEV_API_KEY` in the environment. **Never print, echo, log or commit the key.**
2. The is-agentic MCP is connected (`is_agentic_get_report` is available).
3. You know how this site's pages are edited and shipped (repository, CMS, branch rules). The
   project's own rules on commits, reviews and releases always win over this skill.

`<skill>` is this skill's directory. Run every script with `--work <dir>`; one workspace per site
(default `./seo-tuning`). Keep the workspace out of version control if the site's repository is
public and the owner has not agreed to publish it.

## Rules that do not bend

- **Keywords are researched blind from the intent, never from the page.** Keywords drafted from the
  page score well and mean nothing: the page always matches itself. The researcher gets the intent
  and the audience, not the URL or the text.
- **Each keyword needs two or more independent sources** (different sites). `tune.py keywords`
  rejects anything less.
- **Scripts score; you do not estimate.** Never state a score, delta or verdict that did not come
  from a script's output.
- **Within the noise floor is level.** A change counts only when seo-jev's verdict is `up`.
- **Metadata edits are automatic. Content edits pause for approval.** The test: does the change
  alter how the page is described, marked up or found (automatic), or what the page says (needs
  the owner's approval, shown as a diff)?
- **No claim the page does not support.** A candidate that promises more than the page delivers,
  or reads worse, is rejected even if it scores higher. No keyword stuffing.

## The loop

### 1. Set up (once per site)

```bash
python <skill>/scripts/tune.py --work seo-tuning init --domain example.com
python <skill>/scripts/tune.py --work seo-tuning boilerplate
```

Choose the pages with the owner; set `"included": false` on the rest in `profile.json`.

### 2. Capture each page's intent (gate: the owner approves)

One question per page that the page must answer, in the searcher's words: "How do I set up X for
Y?", not "X guide". Draft them from the page title and headings, then **ask the owner to approve
or edit every intent**. Every score depends on them. Write the approved intents into
`profile.json`.

### 3. Research keywords, blind

For each page, hand the intent to a subagent on a cheaper model (Sonnet or Haiku) with
[references/keyword-research.md](references/keyword-research.md) as its brief. It searches the
web, never the page, and writes `keywords/<slug>.json`. Run pages in parallel. Then:

```bash
python <skill>/scripts/tune.py --work seo-tuning keywords          # validate
python <skill>/scripts/tune.py --work seo-tuning keywords --apply  # write into the profile
```

### 4. Baseline

```bash
python <skill>/scripts/tune.py --work seo-tuning live --pass 0
python <skill>/scripts/tune.py --work seo-tuning report --title "<site> tuning"
```

Ask the owner to run an is-agentic scan of the site at is-agentic.com (scans are public and are
started by a person, not by the MCP), then read it with `is_agentic_get_report`. Fix failed
technical checks once, alongside pass 1, under the same automatic/approval test. Record the
is-agentic score in your summary.

**Publish the report now** (see Report), so the owner can watch it from the baseline onwards.

### 5. Passes (repeat)

For pass N (1, 2, ...):

1. **Pick pages.** Run `status`. Work on pages not marked DONE, most headroom (whole page minus
   metadata) first.
2. **Draft 2 or 3 candidates per page** with a writer subagent (Sonnet). Give it, per page: the
   intent, the live title and description, the keywords the page **covers** (to use) and those it
   does **not** (never to claim), and the house style if the site has one. What works: a
   description that **answers the intent directly**, often as the steps or the answer itself,
   in the site's voice. Keep any required title prefix or series naming.
   Save as a JSON list: `[{"slug": "...", "id": "c1", "title": "...", "description": "..."}]`.
   For a content edit, give `"revision": {"body": "..."}` (or any field) instead of title and
   description.
3. **Test against the live page.**

   ```bash
   python <skill>/scripts/tune.py --work seo-tuning trials --pass N --candidates cands.json
   ```

   Each candidate runs through `test_revision` with the latest live score as baseline. A
   **winner** goes up on metadata beyond the noise threshold and does not go down on the whole
   page; the script marks the best winner per page.
4. **Ship winners.** Metadata winners: apply them to the site's source and ship through the
   project's normal delivery. Content winners: show the owner a diff of the change and the trial
   result, and wait. Record what happened, with the before and after text:

   ```bash
   python <skill>/scripts/tune.py --work seo-tuning record --pass N --slug <slug> --json decision.json
   ```

   `decision.json`: `{"notes": ["..."], "decisions": [{"kind": "metadata", "status": "kept",
   "title": "Winner c2", "diff": [["old title", "new title"], ["old description", "new
   description"]]}], "pr": "<link>"}`. Status is `approved`, `kept`, `rejected` or `stopped`.
5. **Measure live** once the change is deployed, then rebuild and republish the report:

   ```bash
   python <skill>/scripts/tune.py --work seo-tuning live --pass N --slug <changed slugs>
   python <skill>/scripts/tune.py --work seo-tuning report --status-text "Pass N live"
   ```

   If live scores disagree with the trial by more than the noise threshold, say so in a note;
   live is the truth.
6. **Backlog.** For each keyword still under 0.5 on the whole page:
   `tune.py backlog --slug <slug> --term "<keyword>" --why "<what the page lacks>"`.

### 6. Stop

`status` prints `STOP` at 20 passes, or when every page is done: its metadata is within the noise
band of its whole-page score, or two passes in a row produced no winner. Then rebuild the report
with `--status-text "Finished: <reason>"`, and summarise: per page, fidelity and coverage from
baseline to now, what shipped, what was rejected and why, the backlog, and the is-agentic score.

## Report

`tune.py report` writes `<work>/report/`: `report.html` and `calc.js` (fixed; never edit them per
site), `data/index.json`, `data/method.json` and `data/<slug>/pass-NN.json`. All arithmetic is in
`calc.js`. Publish the folder at the baseline and update it after every pass:

- in Claude, as a multi-file artifact (the page plus `calc.js` and `data/` as supporting files);
- or on any static host; or locally with `python -m http.server -d <work>/report`. Opening the file
  directly does not work, because the page fetches its data.

## Token budget

You orchestrate and decide; read one-line summaries, not raw results. Scripts make every seo-jev
call in parallel. Keyword research and candidate drafting go to cheaper-model subagents. Do not
open `runs/*.json` unless a summary line needs explaining.

## Files

- [references/formats.md](references/formats.md): workspace layout and every file format.
- [references/keyword-research.md](references/keyword-research.md): the brief for keyword
  researchers.
- `scripts/jevclient.py`: MCP client. `scripts/tune.py`: the loop. `scripts/tunelib.py`: pure
  functions (tested).

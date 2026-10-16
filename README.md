# seo-tuning-skill

A [Claude Code](https://claude.com/claude-code) skill that tunes a website's pages for search
engines and AI answer engines, one measured pass at a time.

It answers a question technical SEO audits don't: **does this page answer what people search
for, and do its title and description say so?** It uses two MCP tools:

- **[seo-jev-analyzer](https://github.com/matthelam/seo-jev-analyzer)** scores a page from 0 to 10
  against a search intent (the question the page should answer) and ten expected keywords. It
  scores the metadata alone and the whole page, and can test a change before you publish it.
- **[is-agentic](https://is-agentic.com)** checks technical readiness: can crawlers and agents
  find, fetch and parse the site.

## What the skill does

1. **Intent.** One question per page, approved by the site owner.
2. **Keywords, researched blind.** Ten per page, found by searching the web from the intent alone,
   never from the page. Each needs two or more independent sources.
3. **Baseline.** Live scores for every page, and an is-agentic report for the site.
4. **Passes.** Draft title and description candidates that answer the intent; test each against
   the live page with `test_revision`; ship the winners; measure live again.
5. **Stop** at 20 passes, or when no change beats the noise floor.

The north star is **fidelity**: metadata score ÷ whole-page score. The whole page is the ceiling;
good metadata gets close to it without claiming more. Keywords the page doesn't cover go to a
**content backlog** instead of into the metadata.

Metadata edits are applied automatically. Content edits stop and show the owner a diff first.
Scripts do all the scoring and comparing, so every number is a tool result, not a guess, and the
agent's tokens go on decisions. A fixed HTML report shows each page's passes, trials, keywords and
backlog, and is rebuilt after every pass.

## Prerequisites

- **Claude Code**, and Python 3.10 or later (the scripts use the standard library only).
- **Your own seo-jev-analyzer deployment.** There is no public hosted instance: every score spends
  Jev credits on the deployment owner's account. Deploy it from
  [the repository](https://github.com/matthelam/seo-jev-analyzer) (its README covers Vercel and
  local setup) with:
  - `TYPESAFE_API_KEY`: your own API key for TypeSafe's Jev model ([docs.typesafe.ai](https://docs.typesafe.ai));
  - `MCP_API_KEY`: a key of 16 characters or more, which turns on the MCP endpoint.
- **The is-agentic MCP server** (public, read-only).

## Install

As a plugin, inside Claude Code:

```
/plugin marketplace add matthelam/seo-tuning-skill
/plugin install seo-tuning@seo-tuning-skill
```

Or copy the skill folder into your personal skills:

```bash
git clone https://github.com/matthelam/seo-tuning-skill
cp -r seo-tuning-skill/skills/seo-tuning ~/.claude/skills/
```

## Configure

Set two environment variables where Claude Code runs. **Never put the key in a file inside a
repository.**

```bash
export SEO_JEV_MCP_URL="https://<your-deployment>/api/mcp"
export SEO_JEV_API_KEY="<one of your MCP_API_KEY values>"
```

On Windows, `setx SEO_JEV_MCP_URL "..."` and `setx SEO_JEV_API_KEY "..."` save them for your user;
the scripts read them even before you restart the shell.

Add is-agentic, and optionally seo-jev-analyzer for ad hoc use (the skill's scripts call
seo-jev-analyzer directly and don't need this):

```bash
claude mcp add --transport http is-agentic https://is-agentic.com/mcp
claude mcp add --transport http seo-jev-analyzer "$SEO_JEV_MCP_URL" --header "Authorization: Bearer $SEO_JEV_API_KEY"
```

Check the connection (this uses no Jev credits):

```bash
python ~/.claude/skills/seo-tuning/scripts/jevclient.py check
```

## Use

Ask Claude Code, in the site's repository: *"Tune the SEO for example.com"*, or *"Run an SEO pass
on the guides section"*. The skill sets up a workspace (`./seo-tuning` by default), asks you to
approve the intents, and reports after every pass. See [SKILL.md](skills/seo-tuning/SKILL.md) for
the full loop and [formats.md](skills/seo-tuning/references/formats.md) for the files it writes.

A workspace holds your pages' scores and research. Keep it out of a public repository unless you
mean to publish it.

## Limits

- seo-jev measures relevance as the Jev model judges it. It is not a search ranking, and it does
  not check facts. See seo-jev-analyzer's [method](https://github.com/matthelam/seo-jev-analyzer/blob/main/docs/method.md).
- The noise floor (changes within it count as level) is measured per Jev version.
- Each score costs Jev credits on your account. A baseline is 3 runs per page; a pass with three
  candidates is about 9 more runs per page.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
python -m unittest discover -s tests -v   # no network, no key needed
node --test tests/calc.test.mjs
```

## Licence

[MIT](LICENSE)

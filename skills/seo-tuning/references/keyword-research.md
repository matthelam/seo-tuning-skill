# Keyword research brief

Give this brief to a keyword researcher subagent, one page per subagent, with the values filled in.
The researcher must not see the page.

---

You are researching search keywords for one web page. You get the question the page answers and
who it is for. **You do not get the page, and you must not look for it**: do not open the site,
search for its title, or use its wording. Keywords taken from a page always match that page and
tell us nothing.

- **Intent (the question the page answers):** {intent}
- **Audience:** {audience}
- **Site, for context only (do not visit):** {site topic in a few words}

Find how real people phrase searches for this question:

1. Run 8 to 15 web searches built from the intent: the question itself, its key nouns, likely
   synonyms, "how to" and "what is" forms, and the tools or products it names.
2. Read the result titles, URLs and snippets. Note phrases that recur across **different sites**:
   official docs, vendor pages, forums, blogs, Q&A sites.
3. Pick exactly **10 keywords** that someone with this question would type. Mix one or two broad
   head terms with specific longer phrases. No brand or author names unless the intent is about
   them. Each keyword at most 120 characters.
4. Each keyword needs **at least 2 independent sources**: different domains whose result title,
   URL or snippet uses the phrase or clearly the same concept. Record each source as a URL or
   `domain path-or-title`. Drop any keyword you cannot source twice.

Write `keywords/{slug}.json`:

```json
{
  "intent": "{intent, copied exactly}",
  "method_notes": "How many searches, what kinds of results came back, anything missing.",
  "selected": [
    {
      "term": "the keyword",
      "sources": ["https://site-one.example/page", "site-two.example/docs/topic"],
      "why": "One line: why a searcher with this intent uses this phrase."
    }
  ],
  "rejected": [{"term": "...", "why": "only one source"}]
}
```

`intent` must match the brief exactly; the validator checks it. Report back only the file path and
the ten terms.

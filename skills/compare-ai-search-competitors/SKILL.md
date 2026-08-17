---
name: compare-ai-search-competitors
description: Compare a website with one or more competitors for AI search readiness, technical accessibility, entity clarity, answerability, citation-worthiness, content depth, topic coverage, and platform crawler access. Use when a user asks for an AI competitor audit, competitive GEO/AEO analysis, head-to-head AI search comparison, or wants to know which site is better prepared for Google AI Search, ChatGPT Search, Claude, or Gemini and why.
---

# Compare AI Search Competitors

## Collect only the required URLs

If the user's website URL is missing, ask: **What is your website URL?**

After receiving it, if competitor URLs are missing, ask: **What competitor website URLs should I compare it against? Send up to five.**

Do not ask for keywords, page limits, scoring choices, platforms, or report formats. Accept one to five competitor URLs and infer the rest.

## Run the comparison

Locate this skill directory and execute:

```bash
python3 scripts/compare.py "<YOUR_URL>" "<COMPETITOR_URL>" ["<ANOTHER_COMPETITOR_URL>"]
```

The comparator applies the same conservative crawl cap and checks to every site. Allow network access if required. It writes:

```text
.ai-search-audit/latest/
  competitor-report.md
  competitor-report.json
  competitor-report.html
```

## Present the result

Summarize:

1. The overall leader and score for each site.
2. Where the user's site leads.
3. Where each competitor leads.
4. The measurable reasons for the differences.
5. Competitor topics the user's crawled sample does not cover.
6. The five highest-impact actions to close the gap.
7. The full report path.

Treat scores as inferred readiness comparisons, not proof of rankings, traffic, citations, or platform inclusion. Keep `MEASURED`, `INFERRED`, and `EXPERIMENTAL` labels intact. When a site blocks or fails the crawl, mark its comparison incomplete instead of declaring it the loser.

Read [references/methodology.md](references/methodology.md) when explaining interpretation boundaries.

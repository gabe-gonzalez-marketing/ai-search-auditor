---
name: run-ai-search-audit
description: Run a complete zero-configuration AI search visibility and readiness audit for a public website. Use when a user asks for an AI search audit, GEO/AEO audit, AI visibility review, ChatGPT Search readiness check, Google AI Overviews or AI Mode audit, Claude/Gemini readiness review, or wants to know whether a site is crawlable, answerable, and citation-worthy. The only required input is the website URL.
---

# Run an AI Search Audit

## Interaction contract

If the user has not supplied a URL, ask exactly: **What website URL would you like me to audit?**

Once a URL is available, do not ask setup questions. Do not request keywords, page limits, providers, API keys, report formats, or check selections. Run the complete audit with intelligent defaults.

## Run the audit

1. Locate this skill directory and execute:

   ```bash
   python3 scripts/audit.py "<URL>"
   ```

2. Allow network access if the environment requires approval. The crawler is read-only, honors `robots.txt`, limits itself to the primary origin, uses a delay, and chooses a conservative crawl cap automatically.
3. Read `.ai-search-audit/latest/report.json` and `.ai-search-audit/latest/report.md` from the current working directory.
4. Present the readiness score, four platform scores, detected business profile, five highest-priority fixes, output path, and optional integrations that were not detected.

Never claim that the audit proves inclusion, ranking, or citation in an AI product. Preserve the report's evidence labels:

- `OFFICIAL`: platform documentation
- `OBSERVED`: directly visible page or response behavior
- `MEASURED`: computed from crawled pages
- `TESTED`: an explicit request made during this run
- `INFERRED`: reasoned readiness assessment
- `EXPERIMENTAL`: heuristic without a validated platform guarantee

## Optional enhancements

Detect credentials without asking. The base audit never requires them. If optional credentials are absent, finish normally and list what they would enable. Never send site content to a third-party model unless the user already authorized that provider or the environment's existing model can analyze it in-place.

## Repository-aware follow-up

When running inside the audited site's source repository, inspect the codebase after the report is complete. Map fixable findings to probable files and state how many findings can be fixed directly. Do not modify the site unless the user asks to fix the issues.

For interpretation rules and official sources, read [references/methodology.md](references/methodology.md).

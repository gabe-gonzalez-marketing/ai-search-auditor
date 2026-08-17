# AI Search Auditor

An installable, zero-configuration agent skill for auditing how ready a website is for Google AI Search, ChatGPT Search, Claude, and Gemini experiences.

The normal interaction is intentionally short:

```text
User: Run an AI search audit.
Agent: What website URL would you like me to audit?
User: https://example.com
```

The URL is the only required input. The skill discovers `robots.txt` and sitemaps, selects a safe crawl limit, analyzes technical and content signals, detects entities and topics, generates intent-led query fan-out, and saves:

```text
.ai-search-audit/latest/
  report.md
  report.json
  report.html
```

## Install

Install this repository as a Codex plugin, then invoke `$run-ai-search-audit` or ask naturally for an AI search audit. The bundled auditor requires Python 3.10+ and no third-party packages or API keys.

For direct use:

```bash
python3 skills/run-ai-search-audit/scripts/audit.py https://example.com
```

Optional advanced flags are available via `--help`, but are not part of standard onboarding.

## Safety and evidence

The crawler is read-only, same-origin, rate-limited, robots-aware, and conservatively capped. Findings explicitly distinguish official guidance, observed behavior, measurements, tests, inferences, and experimental heuristics. Readiness scores are not claims of platform inclusion, ranking, or citation.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 skills/run-ai-search-audit/scripts/audit.py --help
```

## License

MIT

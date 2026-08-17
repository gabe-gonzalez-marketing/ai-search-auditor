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

## Requirements

- Python 3.10 or newer
- Network access to the public website you want to audit
- No third-party Python packages or API keys

## Use with Codex

### Install

In a terminal, add this repository as a plugin marketplace and install the plugin:

```bash
codex plugin marketplace add gabe-gonzalez-marketing/ai-search-auditor
codex plugin add ai-search-auditor@ai-search-auditor
```

Start a new Codex session after installation. In the Codex app, you can also open the Plugins Directory after adding the marketplace and install **AI Search Auditor** from there.

### Run

Ask naturally:

```text
Run an AI search audit.
```

Codex will ask for the website URL if you did not include it. You can also invoke the skill explicitly:

```text
Use $run-ai-search-audit to audit https://example.com
```

### Update

```bash
codex plugin marketplace upgrade ai-search-auditor
```

Then update or reinstall the plugin from the plugin browser if a newer version is available, and start a new session.

## Use with Claude Code

### Install

Start Claude Code, then run these commands inside its interactive prompt:

```text
/plugin marketplace add gabe-gonzalez-marketing/ai-search-auditor
/plugin install ai-search-auditor@ai-search-auditor
/reload-plugins
```

Choose **User** scope when prompted to make the plugin available in all of your projects. Claude Code namespaces installed plugin skills, so the explicit skill command is:

```text
/ai-search-auditor:run-ai-search-audit
```

You can also ask naturally:

```text
Run an AI search audit for https://example.com
```

If you omit the URL, Claude asks for it and then runs the complete audit without additional setup questions.

### Update

```text
/plugin marketplace update ai-search-auditor
/plugin update ai-search-auditor@ai-search-auditor
/reload-plugins
```

## Run directly

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

# Methodology and source policy

## Evidence policy

Treat crawl results as a point-in-time sample. A successful fetch does not prove indexing; a robots allowance does not prove a crawler will visit; readiness does not prove ranking or citation. Report unavailable checks rather than silently scoring them as failures.

## Official platform guidance

- Google states that standard SEO fundamentals remain applicable to AI Overviews and AI Mode and that no special AI markup is required: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Google crawling, indexing, canonical, sitemap, robots, and snippet controls: https://developers.google.com/search/docs/crawling-indexing
- OpenAI says content intended for ChatGPT Search summaries and snippets should not block `OAI-SearchBot`; training controls for `GPTBot` are distinct: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
- Anthropic documents separate `ClaudeBot`, `Claude-User`, and `Claude-SearchBot` purposes and their robots behavior: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler

Recheck these URLs when providing detailed platform-specific remediation because crawler names and product guidance can change.

## Heuristic boundaries

Answerability and citation-worthiness are `EXPERIMENTAL` heuristics. They use visible text structure, question/answer patterns, specificity, headings, lists, schema, authorship-like signals, dates, and external references. They are prioritization aids, not platform ranking factors.

Query fan-out is generated from detected title, heading, navigation, schema, and repeated-content terms. It maps intent coverage inside the crawled sample; it does not represent measured search demand.

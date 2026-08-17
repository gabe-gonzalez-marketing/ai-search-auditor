import importlib.util
import pathlib
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "skills/run-ai-search-audit/scripts/audit.py"
spec = importlib.util.spec_from_file_location("audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_normalize_adds_scheme_and_path(self):
        self.assertEqual(audit.normalize_url("Example.com"), "https://example.com/")

    def test_normalize_rejects_localhost(self):
        with self.assertRaises(ValueError):
            audit.normalize_url("http://localhost:8000")

    def test_canonicalize_removes_tracking(self):
        self.assertEqual(audit.canonicalize("https://EXAMPLE.com/a/?utm_source=x&q=1#x"), "https://example.com/a?q=1")

    def test_parser_extracts_core_signals(self):
        p = audit.PageParser()
        p.feed('''<html><head><title>Widget Guide</title><meta name="robots" content="index,follow"><link rel="canonical" href="/guide"><script type="application/ld+json">{"@type":"Article"}</script></head><body><h1>Widgets</h1><a href="/buy">Buy</a><p>Useful answer.</p></body></html>''')
        self.assertEqual(p.title, "Widget Guide")
        self.assertEqual(p.canonical, "/guide")
        self.assertEqual(p.meta["robots"], "index,follow")
        self.assertTrue(p.jsonld)

    def test_report_bundle(self):
        data = {"scores":{"overall":80,"google_ai_search":82,"chatgpt_search":78,"claude":77,"gemini":82,"evidence":"INFERRED"},
                "site_profile":{"detected_business":"Organization","site_name":"Example","primary_topics":["widgets"]},
                "issues":[],"crawl":{"pages_fetched":1,"successful_html":1,"sitemap_urls_discovered":1},
                "optional_integrations":{},"limitations":[],"official_guidance":{},"primary_domain":"example.com","generated_at":"now"}
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td); audit.write_reports(data,out)
            self.assertEqual({p.name for p in out.iterdir()},{"report.md","report.json","report.html"})


if __name__ == "__main__": unittest.main()

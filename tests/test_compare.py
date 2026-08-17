import importlib.util
import pathlib
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "skills/compare-ai-search-competitors/scripts/compare.py"
spec = importlib.util.spec_from_file_location("compare", SCRIPT)
compare = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = compare
spec.loader.exec_module(compare)


def site(domain, score, canonical, schema, topics):
    return {"primary_domain":domain,"comparison_complete":True,
            "scores":{"overall":score,"google_ai_search":score,"chatgpt_search":score,"claude":score,"gemini":score},
            "crawl":{"successful_html":10},
            "metrics":{"canonical_coverage":canonical,"structured_data_coverage":schema,
                       "answerability_coverage":.5,"citation_worthiness_coverage":.4,
                       "thin_pages":2,"orphan_sample":1},
            "site_profile":{"primary_topics":topics},"issues":[]}


class CompareTests(unittest.TestCase):
    def test_leader_reasons_and_topic_gaps(self):
        primary=site("mine.test",70,.5,.4,["widgets"])
        rival=site("rival.test",82,.9,.8,["widgets","pricing"])
        result=compare.build_comparison(primary,[rival])
        self.assertEqual(result["leader"],"rival.test")
        self.assertTrue(any(x["leader"]=="competitor" for x in result["metric_differences"]))
        self.assertEqual(result["primary_topic_gaps"][0]["topic"],"pricing")

    def test_incomplete_site_cannot_win(self):
        primary=site("mine.test",60,.5,.5,["widgets"])
        rival=site("blocked.test",100,1,1,["widgets"]); rival["comparison_complete"]=False
        self.assertEqual(compare.build_comparison(primary,[rival])["leader"],"mine.test")

    def test_writes_all_report_formats(self):
        primary=site("mine.test",70,.7,.7,["widgets"])
        data=compare.build_comparison(primary,[site("rival.test",65,.6,.6,["gadgets"])])
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td); compare.write_reports(data,out)
            self.assertEqual({x.name for x in out.iterdir()},{"competitor-report.md","competitor-report.json","competitor-report.html"})


if __name__=="__main__": unittest.main()

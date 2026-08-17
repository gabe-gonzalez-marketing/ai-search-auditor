#!/usr/bin/env python3
"""Compare AI search readiness across equally crawled websites."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from pathlib import Path

AUDIT_PATH = Path(__file__).parents[2] / "run-ai-search-audit" / "scripts" / "audit.py"
SPEC = importlib.util.spec_from_file_location("ai_search_audit_core", AUDIT_PATH)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def run_site(url, limit, delay, timeout):
    runner = audit.Auditor(url, hard_limit=limit, delay=delay, timeout=timeout)
    actual_limit = runner.crawl()
    result = audit.analyze(runner, actual_limit)
    result["comparison_complete"] = result["crawl"]["successful_html"] > 0
    return result


def metric_rows(result):
    m = result["metrics"]
    pages = max(1, result["crawl"]["successful_html"])
    return {
        "Canonical coverage": m["canonical_coverage"],
        "Structured data coverage": m["structured_data_coverage"],
        "Answerability coverage": m["answerability_coverage"],
        "Citation-worthiness coverage": m["citation_worthiness_coverage"],
        "Thin-page avoidance": max(0, 1 - m["thin_pages"] / pages),
        "Internal discoverability": max(0, 1 - m["orphan_sample"] / pages),
    }


def build_comparison(primary, competitors):
    sites = [primary, *competitors]
    complete = [x for x in sites if x["comparison_complete"]]
    ranked = sorted(complete, key=lambda x: x["scores"]["overall"], reverse=True)
    leader = ranked[0] if ranked else None
    primary_metrics = metric_rows(primary)
    reasons = []
    for site in competitors:
        if not site["comparison_complete"]: continue
        theirs = metric_rows(site)
        for label, own in primary_metrics.items():
            delta = round((own - theirs[label]) * 100)
            if abs(delta) >= 10:
                reasons.append({"metric":label,"primary":round(own*100),"competitor":round(theirs[label]*100),
                                "competitor_domain":site["primary_domain"],"delta":delta,
                                "leader":"primary" if delta>0 else "competitor","evidence":"MEASURED"})
    own_topics = set(primary["site_profile"]["primary_topics"])
    gaps = []
    for site in competitors:
        for topic in site["site_profile"]["primary_topics"]:
            if topic not in own_topics:
                gaps.append({"topic":topic,"seen_on":site["primary_domain"],"evidence":"INFERRED"})
    priorities=[]
    for reason in sorted((r for r in reasons if r["leader"]=="competitor"), key=lambda x:x["delta"]):
        priorities.append(f"Close the {reason['metric'].lower()} gap versus {reason['competitor_domain']} ({abs(reason['delta'])} points).")
    for issue in primary["issues"]:
        priorities.append(issue["title"] + ": " + issue["detail"])
    priorities=list(dict.fromkeys(priorities))[:5]
    return {"schema_version":"1.0","generated_at":audit.now_iso(),"evidence":"INFERRED",
            "leader":leader["primary_domain"] if leader else None,
            "ranking":[{"domain":x["primary_domain"],"overall":x["scores"]["overall"],
                        "complete":x["comparison_complete"]} for x in sorted(sites,key=lambda x:x["scores"]["overall"],reverse=True)],
            "metric_differences":reasons,"primary_topic_gaps":gaps[:20],"priorities":priorities,
            "primary":primary,"competitors":competitors,
            "limitations":["This identifies a readiness leader, not a traffic, ranking, or market-share leader.",
                           "Scores compare equally capped HTML crawl samples and are inferred.",
                           "Topic gaps are inferred from visible titles, headings, descriptions, and structured data."]}


def render_md(data):
    primary=data["primary"]; lines=["# AI Search Competitor Comparison","",
        f"**Readiness leader:** {data['leader'] or 'Unavailable — no successful crawl'} `[{data['evidence']}]`","",
        "## Scorecard","","| Site | Overall | Google AI | ChatGPT | Claude | Gemini | Crawl |","|---|---:|---:|---:|---:|---:|---|"]
    for site in [primary,*data["competitors"]]:
        s=site["scores"]; state="complete" if site["comparison_complete"] else "incomplete"
        lines.append(f"| {site['primary_domain']} | {s['overall']} | {s['google_ai_search']} | {s['chatgpt_search']} | {s['claude']} | {s['gemini']} | {state} |")
    lines += ["","## Why scores differ",""]
    if data["metric_differences"]:
        for row in data["metric_differences"]:
            direction="leads" if row["leader"]=="primary" else "trails"
            lines.append(f"- **{row['metric']}**: {primary['primary_domain']} {direction} {row['competitor_domain']} by {abs(row['delta'])} points ({row['primary']} vs {row['competitor']}). `[MEASURED]`")
    else: lines.append("- No metric differed by at least 10 points in the successful crawl samples.")
    lines += ["","## Competitor topic gaps",""]
    lines += [f"- **{x['topic']}** — detected on {x['seen_on']} `[INFERRED]`" for x in data["primary_topic_gaps"]] or ["- No distinct competitor topics were detected in the sample."]
    lines += ["","## Priorities for " + primary["primary_domain"],""]
    lines += [f"{i}. {x}" for i,x in enumerate(data["priorities"],1)] or ["1. No high-confidence priority was identified."]
    lines += ["","## Limitations",""]+[f"- {x}" for x in data["limitations"]]
    return "\n".join(lines)+"\n"


def render_html(data):
    rows="".join(f"<tr><td>{html.escape(x['domain'])}</td><td>{x['overall']}</td><td>{'Complete' if x['complete'] else 'Incomplete'}</td></tr>" for x in data["ranking"])
    why="".join(f"<li><b>{html.escape(x['metric'])}</b>: {html.escape(data['primary']['primary_domain'])} {'leads' if x['leader']=='primary' else 'trails'} {html.escape(x['competitor_domain'])} by {abs(x['delta'])} points.</li>" for x in data["metric_differences"])
    priorities="".join(f"<li>{html.escape(x)}</li>" for x in data["priorities"])
    return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>AI Search Competitor Comparison</title><style>body{{font:16px/1.55 system-ui;background:#f4f7fb;color:#172033;margin:0}}main{{max-width:960px;margin:auto;padding:40px 24px}}section{{background:#fff;border:1px solid #dce3ed;border-radius:14px;padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #e5eaf1;text-align:left}}h1{{font-size:34px}}.lead{{font-size:22px;color:#146b55}}</style><main><h1>AI Search Competitor Comparison</h1><p class=lead>Readiness leader: <b>{html.escape(data['leader'] or 'Unavailable')}</b></p><section><h2>Scorecard</h2><table><tr><th>Site</th><th>Overall</th><th>Crawl</th></tr>{rows}</table></section><section><h2>Why scores differ</h2><ul>{why or '<li>No large measured differences.</li>'}</ul></section><section><h2>Priorities</h2><ol>{priorities or '<li>No high-confidence priority identified.</li>'}</ol></section><p>Readiness comparison only; not proof of rankings, traffic, citations, or market leadership.</p></main></html>"""


def write_reports(data, output):
    output.mkdir(parents=True,exist_ok=True)
    (output/"competitor-report.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (output/"competitor-report.md").write_text(render_md(data),encoding="utf-8")
    (output/"competitor-report.html").write_text(render_html(data),encoding="utf-8")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Compare AI search readiness against competitors.")
    parser.add_argument("primary_url"); parser.add_argument("competitor_urls",nargs="+")
    parser.add_argument("--limit",type=int,default=25,help="Equal per-site crawl cap")
    parser.add_argument("--delay",type=float,default=.2); parser.add_argument("--timeout",type=int,default=15)
    parser.add_argument("--output",default=".ai-search-audit/latest")
    args=parser.parse_args(argv)
    if len(args.competitor_urls)>5: parser.error("Provide no more than five competitor URLs.")
    try:
        primary=run_site(args.primary_url,args.limit,args.delay,args.timeout)
        competitors=[run_site(url,args.limit,args.delay,args.timeout) for url in args.competitor_urls]
        data=build_comparison(primary,competitors); write_reports(data,Path(args.output))
        print(f"READINESS LEADER: {data['leader'] or 'unavailable'}")
        for row in data["ranking"]: print(f"{row['domain']}: {row['overall']}/100 ({'complete' if row['complete'] else 'incomplete'})")
        print(f"Full report: {Path(args.output)/'competitor-report.html'}")
        return 0
    except (ValueError,KeyboardInterrupt) as e:
        print(f"Comparison failed: {e}",file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())

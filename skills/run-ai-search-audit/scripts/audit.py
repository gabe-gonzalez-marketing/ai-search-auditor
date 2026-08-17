#!/usr/bin/env python3
"""Zero-dependency, read-only AI search readiness auditor."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

VERSION = "0.1.0"
UA = f"AISearchAuditor/{VERSION} (+https://github.com/gabe-gonzalez-marketing/ai-search-auditor)"
BOT_AGENTS = ["Googlebot", "OAI-SearchBot", "GPTBot", "ClaudeBot", "Claude-User", "Claude-SearchBot"]
TRACKING_KEYS = {"fbclid", "gclid", "msclkid"}
STOP = set("a an and are as at be by for from has have how i in is it its of on or our that the their this to was we what when where which who why will with you your".split())
OFFICIAL = {
    "google": "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide",
    "openai": "https://help.openai.com/en/articles/12627856-publishers-and-developers-faq",
    "anthropic": "https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
}


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    p = urllib.parse.urlsplit(raw)
    if p.scheme.lower() not in {"http", "https"} or not p.hostname:
        raise ValueError("Provide a valid public http(s) website URL.")
    host = p.hostname.encode("idna").decode("ascii").lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ValueError("Local and private targets are not supported by the safe crawler.")
    netloc = host + ((":" + str(p.port)) if p.port else "")
    path = re.sub(r"/{2,}", "/", p.path or "/")
    return urllib.parse.urlunsplit((p.scheme.lower(), netloc, path, p.query, ""))


def canonicalize(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    pairs = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS]
    path = p.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urllib.parse.urlencode(pairs), ""))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""; self.h1 = []; self.headings = []; self.links = []; self.canonical = ""
        self.meta = {}; self.jsonld = []; self.visible = []; self.in_title = False
        self.skip = 0; self.current_script_type = ""; self.script = []; self.current_heading = ""

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}: self.skip += 1
        if tag == "title": self.in_title = True
        if tag in {"h1", "h2", "h3"}: self.current_heading = tag; self.headings.append((tag, ""))
        if tag == "a" and a.get("href"): self.links.append((a["href"], a.get("rel", "")))
        if tag == "link" and "canonical" in a.get("rel", "").lower(): self.canonical = a.get("href", "")
        if tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key: self.meta[key] = a.get("content", "")
        if tag == "script":
            self.current_script_type = a.get("type", "").lower(); self.script = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title": self.in_title = False
        if tag == self.current_heading: self.current_heading = ""
        if tag == "script":
            if "ld+json" in self.current_script_type:
                self.jsonld.append("".join(self.script).strip())
            self.current_script_type = ""; self.script = []
        if tag in {"script", "style", "noscript", "svg"}: self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        clean = re.sub(r"\s+", " ", data).strip()
        if not clean: return
        if self.current_script_type: self.script.append(data)
        if self.skip: return
        if self.in_title: self.title += (" " if self.title else "") + clean
        if self.current_heading and self.headings:
            tag, value = self.headings[-1]
            self.headings[-1] = (tag, (value + " " + clean).strip())
        self.visible.append(clean)


@dataclass
class Page:
    url: str
    final_url: str = ""
    status: int = 0
    content_type: str = ""
    elapsed_ms: int = 0
    title: str = ""
    h1: list[str] = field(default_factory=list)
    canonical: str = ""
    robots: str = ""
    description: str = ""
    word_count: int = 0
    internal_links: list[str] = field(default_factory=list)
    external_links: int = 0
    schema_types: list[str] = field(default_factory=list)
    text_excerpt: str = ""
    error: str = ""


class Auditor:
    def __init__(self, start: str, hard_limit: int = 0, delay: float = 0.2, timeout: int = 15):
        self.start = normalize_url(start); p = urllib.parse.urlsplit(self.start)
        self.origin = f"{p.scheme}://{p.netloc}"; self.host = p.hostname or ""
        self.delay = max(0.1, delay); self.timeout = timeout; self.hard_limit = hard_limit
        self.opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        self.pages = []; self.robots_url = self.origin + "/robots.txt"; self.robots_text = ""
        self.robot = urllib.robotparser.RobotFileParser(); self.sitemaps = []; self.sitemap_urls = []
        self.tested = []

    def request(self, url, user_agent=UA):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.1"})
        begin = time.monotonic()
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                body = r.read(2_500_000); status = getattr(r, "status", 200)
                return status, r.geturl(), r.headers, body, int((time.monotonic()-begin)*1000), ""
        except urllib.error.HTTPError as e:
            return e.code, e.geturl(), e.headers, e.read(200_000), int((time.monotonic()-begin)*1000), str(e)
        except Exception as e:
            return 0, url, {}, b"", int((time.monotonic()-begin)*1000), f"{type(e).__name__}: {e}"

    def discover(self):
        status, _, _, body, _, _ = self.request(self.robots_url)
        self.tested.append({"label":"robots.txt fetch", "evidence":"TESTED", "url":self.robots_url, "status":status})
        if status == 200:
            self.robots_text = body.decode("utf-8", "replace")
            self.robot.set_url(self.robots_url); self.robot.parse(self.robots_text.splitlines())
            self.sitemaps.extend(re.findall(r"(?im)^\s*sitemap:\s*(\S+)", self.robots_text))
        else:
            self.robot.parse([])
        for candidate in [self.origin+"/sitemap.xml", self.origin+"/sitemap_index.xml"]:
            if candidate not in self.sitemaps: self.sitemaps.append(candidate)
        seen_maps = set()
        for sm in list(self.sitemaps)[:8]:
            if sm in seen_maps: continue
            seen_maps.add(sm); status, _, _, body, _, _ = self.request(sm)
            self.tested.append({"label":"sitemap fetch", "evidence":"TESTED", "url":sm, "status":status})
            if status != 200: continue
            try:
                root = ET.fromstring(body)
                locs = [re.sub(r"\s+", "", x.text or "") for x in root.iter() if x.tag.endswith("loc")]
                if root.tag.endswith("sitemapindex"):
                    for child in locs[:5]:
                        s2, _, _, b2, _, _ = self.request(child)
                        if s2 == 200:
                            r2 = ET.fromstring(b2)
                            self.sitemap_urls += [x.text.strip() for x in r2.iter() if x.tag.endswith("loc") and x.text]
                else: self.sitemap_urls += locs
            except (ET.ParseError, ValueError): pass

    def same_site(self, url):
        p = urllib.parse.urlsplit(url)
        return p.scheme in {"http","https"} and (p.hostname or "").lower() == self.host.lower()

    def crawl(self):
        self.discover()
        auto = 25 if not self.sitemap_urls else min(100, max(25, int(len(set(self.sitemap_urls)) ** 0.5 * 10)))
        limit = self.hard_limit or auto
        queue = collections.deque([self.start] + self.sitemap_urls[:limit]); seen = set()
        while queue and len(self.pages) < limit:
            url = canonicalize(queue.popleft())
            if url in seen or not self.same_site(url): continue
            seen.add(url)
            if self.robots_text and not self.robot.can_fetch(UA, url): continue
            status, final, headers, body, elapsed, error = self.request(url)
            ctype = (headers.get("Content-Type", "") if headers else "").lower()
            page = Page(url=url, final_url=final, status=status, content_type=ctype, elapsed_ms=elapsed, error=error)
            if "html" in ctype and body:
                parser = PageParser()
                try: parser.feed(body.decode("utf-8", "replace"))
                except Exception: pass
                text = re.sub(r"\s+", " ", " ".join(parser.visible)).strip()
                page.title = parser.title[:300]; page.h1 = [v for t,v in parser.headings if t=="h1" and v]
                page.canonical = urllib.parse.urljoin(final, parser.canonical) if parser.canonical else ""
                page.robots = ", ".join(x for x in [parser.meta.get("robots",""), headers.get("X-Robots-Tag","") if headers else ""] if x)
                page.description = parser.meta.get("description", "")[:500]
                page.word_count = len(re.findall(r"\b[\w'-]+\b", text)); page.text_excerpt = text[:800]
                schemas = []
                for raw in parser.jsonld:
                    try:
                        data = json.loads(raw)
                        stack = data if isinstance(data, list) else [data]
                        while stack:
                            item = stack.pop()
                            if isinstance(item, dict):
                                typ = item.get("@type", [])
                                schemas += typ if isinstance(typ, list) else ([typ] if typ else [])
                                for value in item.values():
                                    if isinstance(value, (dict,list)): stack.extend(value if isinstance(value,list) else [value])
                    except (json.JSONDecodeError, TypeError): pass
                page.schema_types = sorted(set(str(x) for x in schemas))
                links = []
                for href, rel in parser.links:
                    absolute = canonicalize(urllib.parse.urljoin(final, href))
                    if self.same_site(absolute) and not re.search(r"\.(?:jpg|jpeg|png|gif|svg|webp|pdf|zip|mp4|mp3)(?:\?|$)", absolute, re.I):
                        links.append(absolute)
                        if "nofollow" not in rel.lower() and absolute not in seen: queue.append(absolute)
                    elif absolute.startswith("http"): page.external_links += 1
                page.internal_links = sorted(set(links))
            self.pages.append(page); time.sleep(self.delay)
        return limit

    def crawler_access(self):
        result = {}
        for agent in BOT_AGENTS:
            result[agent] = {"allowed_home": self.robot.can_fetch(agent, self.start) if self.robots_text else True,
                             "evidence":"MEASURED", "source": self.robots_url}
        return result


def topic_profile(pages):
    corpus = " ".join(" ".join([p.title, *p.h1, p.description]) for p in pages)
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", corpus) if w.lower() not in STOP]
    topics = [w for w,_ in collections.Counter(words).most_common(12)]
    home = pages[0] if pages else Page("")
    schema = sorted({t for p in pages for t in p.schema_types})
    business = next((t for t in schema if t not in {"WebSite","WebPage","BreadcrumbList","Organization","Person"}), "Website")
    return {"detected_business": business, "site_name": home.title or urllib.parse.urlsplit(home.url).hostname,
            "primary_topics": topics[:8], "schema_entities": schema[:20], "evidence":"INFERRED"}


def query_fanout(profile, pages):
    topics = profile["primary_topics"][:5] or ["services"]
    patterns = [("informational","what is {t}"),("commercial","best {t}"),("comparison","{t} alternatives"),
                ("pricing","{t} pricing"),("buying","how to choose {t}"),("problem-solving","{t} problems"),
                ("implementation","how to use {t}")]
    rows=[]
    for topic in topics:
        for intent, pattern in patterns:
            q=pattern.format(t=topic); tokens=set(q.split())-STOP; best=None; score=0
            for p in pages:
                hay=(p.title+" "+" ".join(p.h1)+" "+p.text_excerpt).lower()
                hit=sum(1 for x in tokens if x in hay)/max(1,len(tokens))
                if hit>score: score=hit; best=p.url
            coverage="covered" if score>=.75 else "partial" if score>=.35 else "missing"
            rows.append({"query":q,"intent":intent,"mapped_url":best if coverage!="missing" else None,
                         "coverage":coverage,"confidence":round(score,2),"evidence":"EXPERIMENTAL"})
    return rows


def analyze(auditor, limit):
    pages=auditor.pages; html_pages=[p for p in pages if "html" in p.content_type]
    ok=[p for p in html_pages if 200<=p.status<300]; count=max(1,len(ok))
    noindex=[p for p in ok if "noindex" in p.robots.lower()]
    canonical=[p for p in ok if p.canonical]; schema=[p for p in ok if p.schema_types]
    thin=[p for p in ok if p.word_count<200]; h1less=[p for p in ok if not p.h1]
    incoming=collections.Counter(x for p in ok for x in p.internal_links)
    orphan=[p for p in ok[1:] if incoming[p.url]==0]
    answerable=[p for p in ok if p.word_count>=300 and (len(p.h1)>0 or "FAQPage" in p.schema_types)]
    citable=[p for p in ok if p.word_count>=500 and (p.external_links>0 or any(x in p.schema_types for x in ["Article","NewsArticle","Report"]))]
    access=auditor.crawler_access(); profile=topic_profile(ok); queries=query_fanout(profile,ok)
    base=100 if ok else 0
    base-=min(20, sum(1 for p in pages if p.status==0 or p.status>=400)*4)
    base-=min(15, len(noindex)*3); base-=10 if not auditor.sitemap_urls else 0
    base-=round(12*(1-len(canonical)/count)); base-=round(10*(1-len(schema)/count))
    base-=round(10*(len(thin)/count)); base-=min(8,len(orphan)*2); overall=max(0,min(100,base))
    google=max(0,min(100,overall+(5 if ok and access["Googlebot"]["allowed_home"] else (-30 if ok else 0))))
    chatgpt=max(0,min(100,overall+(5 if ok and access["OAI-SearchBot"]["allowed_home"] else (-30 if ok else 0))))
    claude=max(0,min(100,overall+(4 if ok and access["Claude-SearchBot"]["allowed_home"] else (-25 if ok else 0))))
    gemini=google
    issues=[]
    def issue(priority,category,title,detail,evidence="MEASURED"):
        issues.append({"priority":priority,"category":category,"title":title,"detail":detail,"evidence":evidence})
    if not ok: issue(1,"crawl","Resolve website fetch failure","No successful HTML page was available, so readiness could not be assessed.","TESTED")
    if ok and not auditor.sitemap_urls: issue(1,"technical","Publish a discoverable XML sitemap","No valid sitemap URLs were discovered.","TESTED")
    if ok and not access["OAI-SearchBot"]["allowed_home"]: issue(1,"crawler","Allow OAI-SearchBot where search visibility is desired","robots.txt blocks the documented ChatGPT Search crawler.")
    if ok and not access["Googlebot"]["allowed_home"]: issue(1,"crawler","Allow Googlebot where search visibility is desired","robots.txt blocks Google Search crawling.")
    if noindex: issue(1,"indexability","Review noindex directives",f"{len(noindex)} crawled HTML page(s) contain noindex.")
    if ok and len(canonical)<count: issue(2,"technical","Add self-referencing canonicals",f"{count-len(canonical)} of {count} successful HTML pages lack a canonical.")
    if ok and len(schema)<count: issue(2,"entity","Add accurate structured data",f"{count-len(schema)} of {count} pages have no detected JSON-LD types.")
    if thin: issue(2,"content","Strengthen thin pages",f"{len(thin)} page(s) contain fewer than 200 visible words.")
    if h1less: issue(3,"content","Add descriptive primary headings",f"{len(h1less)} page(s) have no detected H1.")
    if orphan: issue(3,"structure","Improve internal linking",f"{len(orphan)} crawled page(s) received no links from the crawled sample.")
    if ok and len(answerable)<count*.6: issue(3,"answerability","Make key pages directly answer common questions","Many pages lack sufficient explanatory text or clear answer structure.","EXPERIMENTAL")
    if ok and len(citable)<count*.4: issue(3,"authority","Add original, attributable evidence","Few pages combine depth with references or article/report entity signals.","EXPERIMENTAL")
    issues.sort(key=lambda x:x["priority"])
    env={"Google Search Console": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GSC_CREDENTIALS")),
         "OpenAI API": bool(os.getenv("OPENAI_API_KEY")),"Anthropic API": bool(os.getenv("ANTHROPIC_API_KEY")),
         "Gemini API": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))}
    return {"schema_version":"1.0","generated_at":now_iso(),"input_url":auditor.start,"primary_domain":auditor.host,
            "crawl":{"requested_limit":limit,"pages_fetched":len(pages),"successful_html":len(ok),"robots_url":auditor.robots_url,
                     "sitemaps":auditor.sitemaps,"sitemap_urls_discovered":len(set(auditor.sitemap_urls)),"safe_delay_seconds":auditor.delay},
            "scores":{"overall":overall,"google_ai_search":google,"chatgpt_search":chatgpt,"claude":claude,"gemini":gemini,
                      "evidence":"INFERRED"},"site_profile":profile,"crawler_access":access,
            "metrics":{"indexable_sample":len(ok)-len(noindex),"canonical_coverage":round(len(canonical)/count,2),
                       "structured_data_coverage":round(len(schema)/count,2),"thin_pages":len(thin),"orphan_sample":len(orphan),
                       "answerability_coverage":round(len(answerable)/count,2),"citation_worthiness_coverage":round(len(citable)/count,2)},
            "issues":issues,"query_fanout":queries,"pages":[asdict(p) for p in pages],"tested_requests":auditor.tested,
            "official_guidance":OFFICIAL,"optional_integrations":env,
            "limitations":["Readiness scores are inferred, not platform rankings or inclusion guarantees.",
                           "The crawler evaluates returned HTML and does not execute JavaScript.",
                           "Query fan-out and answerability/citation metrics are experimental heuristics."]}


def render_md(d):
    s=d["scores"]; p=d["site_profile"]; lines=[f"# AI Search Readiness: {s['overall']}/100","",
        f"- Google AI Search: **{s['google_ai_search']}**",f"- ChatGPT Search Readiness: **{s['chatgpt_search']}**",
        f"- Claude Readiness: **{s['claude']}**",f"- Gemini Readiness: **{s['gemini']}**","","## Detected site profile","",
        f"- Business/entity type: {p['detected_business']}",f"- Site: {p['site_name']}",
        f"- Primary topics: {', '.join(p['primary_topics']) or 'Insufficient crawl text'}","","## Top priorities",""]
    if d["issues"]:
        for i,x in enumerate(d["issues"][:5],1): lines.append(f"{i}. **{x['title']}** — {x['detail']} `[{x['evidence']}]`")
    else: lines.append("No high-confidence problems were detected in the crawled sample.")
    lines += ["","## Crawl summary","",f"- Pages fetched: {d['crawl']['pages_fetched']}",
              f"- Successful HTML pages: {d['crawl']['successful_html']}",f"- Sitemap URLs discovered: {d['crawl']['sitemap_urls_discovered']}","",
              "## Optional integrations","" ]
    absent=[k for k,v in d["optional_integrations"].items() if not v]
    lines += [f"- {x}: not detected" for x in absent] or ["- Available credentials were detected; no third-party model calls were made by the base audit."]
    lines += ["","The core audit completed without requiring these integrations.","","## Evidence and limitations",""]
    lines += [f"- {x}" for x in d["limitations"]]
    lines += ["","## Official guidance","",*[f"- [{k.title()}]({v})" for k,v in d["official_guidance"].items()]]
    return "\n".join(lines)+"\n"


def render_html(d, md):
    issues="".join(f"<li><strong>{html.escape(x['title'])}</strong> — {html.escape(x['detail'])} <code>{x['evidence']}</code></li>" for x in d["issues"][:10])
    cards="".join(f"<div class=card><span>{html.escape(k.replace('_',' ').title())}</span><b>{v}</b></div>" for k,v in d["scores"].items() if k!="evidence")
    return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>AI Search Audit — {html.escape(d['primary_domain'])}</title><style>body{{font:16px/1.55 system-ui;margin:0;background:#f4f7fb;color:#152033}}main{{max-width:1000px;margin:auto;padding:40px 24px}}h1{{font-size:36px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}}.card{{background:white;border:1px solid #dce3ed;border-radius:14px;padding:18px;box-shadow:0 4px 18px #2030500c}}.card span{{display:block;color:#596579}}.card b{{font-size:32px;color:#146b55}}section{{background:white;margin-top:20px;padding:24px;border-radius:14px;border:1px solid #dce3ed}}code{{background:#edf1f7;padding:2px 5px;border-radius:4px}}li{{margin:.7em 0}}small{{color:#657084}}</style>
<main><h1>AI Search Readiness</h1><p>{html.escape(d['primary_domain'])} · generated {html.escape(d['generated_at'])}</p><div class=grid>{cards}</div><section><h2>Top priorities</h2><ol>{issues or '<li>No high-confidence issues detected.</li>'}</ol></section><section><h2>Detected profile</h2><p><b>{html.escape(d['site_profile']['detected_business'])}</b></p><p>{html.escape(', '.join(d['site_profile']['primary_topics']))}</p></section><section><h2>Scope</h2><p>{d['crawl']['pages_fetched']} pages fetched; {d['crawl']['sitemap_urls_discovered']} sitemap URLs discovered.</p><small>Scores are inferred readiness assessments, not ranking or inclusion guarantees. See report.json for page-level evidence.</small></section></main></html>"""


def write_reports(data, out):
    out.mkdir(parents=True, exist_ok=True); md=render_md(data)
    (out/"report.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"report.md").write_text(md,encoding="utf-8"); (out/"report.html").write_text(render_html(data,md),encoding="utf-8")


def main(argv=None):
    ap=argparse.ArgumentParser(description="Run a zero-configuration AI search readiness audit.")
    ap.add_argument("url"); ap.add_argument("--limit",type=int,default=0,help="Power-user crawl cap (automatic by default)")
    ap.add_argument("--delay",type=float,default=.2,help="Seconds between requests (minimum 0.1)")
    ap.add_argument("--timeout",type=int,default=15); ap.add_argument("--output",default=".ai-search-audit/latest")
    args=ap.parse_args(argv)
    try:
        auditor=Auditor(args.url,args.limit,args.delay,args.timeout); limit=auditor.crawl(); data=analyze(auditor,limit)
        write_reports(data,Path(args.output)); s=data["scores"]
        print(f"AI SEARCH READINESS: {s['overall']}/100")
        print(f"Google AI Search: {s['google_ai_search']} | ChatGPT: {s['chatgpt_search']} | Claude: {s['claude']} | Gemini: {s['gemini']}")
        print(f"Full report: {Path(args.output)/'report.html'}")
        return 0
    except (ValueError,KeyboardInterrupt) as e:
        print(f"Audit failed: {e}",file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())

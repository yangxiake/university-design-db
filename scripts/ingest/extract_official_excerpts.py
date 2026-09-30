#!/usr/bin/env python3
"""Collect short, source-linked founding and motto leads from official pages.

Rows are extraction leads only. They are not automatically promoted to profile
facts, because a predecessor, merged school, or subordinate college may be
mentioned on the same page.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import html.parser
import pathlib
import re

from discover_official_pages import allowed_by_robots, fetch_page


ROOT = pathlib.Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / "data/review/official-page-discovery-2026.csv"
OUTPUT = ROOT / "data/review/official-excerpts-2026.csv"
YEAR = re.compile(r"(?:始建|始|创办|创立|成立|创建|建校|设立|批准设立)于?\s*(\d{4})年")
YEAR_BEFORE = re.compile(r"(\d{4})年[^。]{0,30}(?:创办|创立|创建|成立|设立|建校)")


class VisibleText(html.parser.HTMLParser):
    BLOCKS = {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "article", "section"}

    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in self.BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.hidden:
            self.parts.append(data)

    def sentences(self):
        raw = "".join(self.parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        for line in lines:
            for sentence in re.split(r"(?<=[。！？])", line):
                sentence = sentence.strip()
                if 15 <= len(sentence) <= 1000:
                    yield sentence


def extract(row):
    base = {"school_code": row["school_code"], "name_zh": row["name_zh"],
            "source_url": row["overview_url"] or row["history_url"] or row["homepage_url"],
            "page_title": "", "field_hint": "", "candidate_year": "",
            "excerpt": "", "status": "no_source", "checked_at": dt.date.today().isoformat(),
            "error_type": ""}
    if row["status"] != "title_matched" or not base["source_url"]:
        return [base]
    url = base["source_url"]
    if not allowed_by_robots(url):
        base["status"] = "robots_disallowed"
        return [base]
    try:
        final_url, html = fetch_page(url)
        parser = VisibleText()
        parser.feed(html)
        base["source_url"] = final_url
        base["page_title"] = parser.title.strip()[:200]
        leads = []
        for sentence in parser.sentences():
            if len(leads) >= 8:
                break
            if any(term in sentence for term in ("始建于", "始于", "创办于", "创立于", "成立于", "创建于", "建校于", "设立于", "批准设立")) or YEAR_BEFORE.search(sentence):
                match = YEAR.search(sentence) or YEAR_BEFORE.search(sentence)
                if match and (row["name_zh"] in sentence or "学校" in sentence or "前身" in sentence):
                    leads.append({**base, "field_hint": "founded_year",
                                  "candidate_year": match.group(1),
                                  "excerpt": sentence[:140], "status": "candidate"})
            elif "校训" in sentence and (row["name_zh"] in sentence or "学校" in sentence or "我校" in sentence):
                leads.append({**base, "field_hint": "motto",
                              "excerpt": sentence[:140], "status": "candidate"})
        if not leads:
            base["status"] = "no_pattern"
            return [base]
        return leads
    except Exception as exc:
        base["status"] = "fetch_error"
        base["error_type"] = type(exc).__name__
        return [base]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    with DISCOVERY.open(encoding="utf-8-sig", newline="") as handle:
        schools = list(csv.DictReader(handle))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        groups = list(pool.map(extract, schools))
    rows = [row for group in groups for row in group]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("Read %d school pages; %d sourced excerpt leads, %d fetch errors." % (
        len(schools), sum(r["status"] == "candidate" for r in rows),
        sum(r["status"] == "fetch_error" for r in rows)))


if __name__ == "__main__":
    main()

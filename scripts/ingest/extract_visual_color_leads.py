#!/usr/bin/env python3
"""Collect short color-code leads from linked school visual identity pages.

Every match is a review lead. The page may mention auxiliary, print, or
department colors, so this script never writes a profile color by itself.
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
OUTPUT = ROOT / "data/review/visual-color-leads-2026.csv"
FIELDS = ["school_code", "name_zh", "source_url", "page_title", "status", "color_space",
          "value", "context", "checked_at", "error_type"]
RGB_LABELED = re.compile(
    r"R\s*[：:=]?\s*(\d{1,3})\s*[,，;/\s]+G\s*[：:=]?\s*(\d{1,3})"
    r"\s*[,，;/\s]+B\s*[：:=]?\s*(\d{1,3})", re.I)
RGB_PLAIN = re.compile(r"RGB\s*(?:色值|数值)?\s*[：:\-=]?\s*(\d{1,3})"
                       r"\s*[,，;/\s]+(\d{1,3})\s*[,，;/\s]+(\d{1,3})", re.I)
HEX = re.compile(r"(?:HEX|网页|色值|色号)\s*[：:\-=]?\s*(#[0-9a-fA-F]{6})(?![0-9a-fA-F])", re.I)


class VisibleText(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.in_title = False
        self.title = ""
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr", "td"} and not self.hidden:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr", "td"} and not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.hidden:
            self.parts.append(data)


def extract(row):
    base = {"school_code": row["school_code"], "name_zh": row["name_zh"],
            "source_url": row["visual_url"], "page_title": "", "status": "no_source",
            "color_space": "", "value": "", "context": "",
            "checked_at": dt.date.today().isoformat(), "error_type": ""}
    if row["status"] != "title_matched" or not row["visual_url"]:
        return [base]
    if not allowed_by_robots(row["visual_url"]):
        base["status"] = "robots_disallowed"
        return [base]
    try:
        final_url, page = fetch_page(row["visual_url"])
        parsed = VisibleText()
        parsed.feed(page)
        text = re.sub(r"\s+", " ", " ".join(parsed.parts)).strip()
        base["source_url"] = final_url
        base["page_title"] = parsed.title.strip()[:160]
        results = []
        seen = set()
        for pattern, color_space in ((RGB_LABELED, "RGB"), (RGB_PLAIN, "RGB"), (HEX, "HEX")):
            for match in pattern.finditer(text):
                if color_space == "RGB":
                    channels = [int(value) for value in match.groups()]
                    if any(value > 255 for value in channels):
                        continue
                    value = "#" + "".join(f"{channel:02X}" for channel in channels)
                else:
                    value = match.group(1).upper()
                context = text[max(0, match.start() - 90):min(len(text), match.end() + 60)]
                key = (value, context)
                if key in seen:
                    continue
                seen.add(key)
                results.append({**base, "status": "candidate", "color_space": color_space,
                                "value": value, "context": context})
                if len(results) >= 12:
                    return results
        if results:
            return results
        base["status"] = "no_pattern"
        return [base]
    except Exception as exc:
        base["status"] = "fetch_error"
        base["error_type"] = type(exc).__name__
        return [base]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    with DISCOVERY.open(encoding="utf-8-sig", newline="") as handle:
        schools = [row for row in csv.DictReader(handle) if row["status"] == "title_matched"
                   and row["visual_url"]]
    groups = {}

    def save():
        rows = [item for school in schools if school["school_code"] in groups
                for item in groups[school["school_code"]]]
        if not rows:
            return
        with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract, row): row["school_code"] for row in schools}
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            groups[futures[future]] = future.result()
            if completed % 20 == 0:
                save()
                print("Checked %d/%d visual pages." % (completed, len(schools)), flush=True)
    save()
    rows = [item for group in groups.values() for item in group]
    print("Processed %d visual pages; %d color-code leads." % (
        len(schools), sum(row["status"] == "candidate" for row in rows)))


if __name__ == "__main__":
    main()

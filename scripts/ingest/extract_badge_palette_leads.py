#!/usr/bin/env python3
"""Sample candidate official header marks for explicitly labelled PPT suggestions.

Images are temporary review material under ignored tmp/. Candidates need visual
identity checks before import. Sampling never establishes an official VI color.
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html.parser
import io
import json
import pathlib
import re
import urllib.request
import urllib.parse

from PIL import Image
from research_all_schools import ROOT, Policy, same_school
from discover_official_pages import AGENT

OUTPUT = ROOT / "data/review/badge-palette-leads-2026.jsonl"
TEMP = ROOT / "tmp/badge-samples"


class Marks(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.styles = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            src = attrs.get("src", "") or attrs.get("data-src", "")
            label = " ".join(attrs.get(k, "") for k in ("alt", "title", "class", "id"))
            if re.search(r"logo|xiaohui|badge|校徽|校标|标识", src + " " + label, re.I):
                self.images.append((src, label))
        if tag == "link" and "stylesheet" in attrs.get("rel", ""):
            self.styles.append(attrs.get("href", ""))
        self.in_title = tag == "title" or self.in_title

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, text):
        if self.in_title:
            self.title += text


def fetch(url, policy, maximum=2_000_000):
    if not policy.allowed(url):
        raise ValueError("robots_disallowed")
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=12) as response:
        data = response.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("size_limit")
        return response.geturl(), data, response.headers.get_content_charset()


def palette(im):
    """Most represented saturated bins; median channel values within each bin."""
    im = im.convert("RGBA")
    im.thumbnail((400, 240))
    pixels = [p[:3] for p in im.getdata() if p[3] >= 192]
    groups = collections.defaultdict(list)
    for r, g, b in pixels:
        hi, lo = max(r, g, b), min(r, g, b)
        if hi < 35 or hi > 245 and lo > 220 or hi - lo < 35:
            continue
        groups[(r // 32, g // 32, b // 32)].append((r, g, b))
    if sum(map(len, groups.values())) < max(20, len(pixels) * .01):
        return []
    ordered = sorted(groups.values(), key=len, reverse=True)
    result = []
    for cluster in ordered:
        rgb = tuple(sorted(p[c] for p in cluster)[len(cluster) // 2] for c in range(3))
        # Adjacent quantization bins are usually shades of the same color.
        if any(sum((a-b)**2 for a, b in zip(rgb, old["rgb"])) < 70**2 for old in result):
            continue
        result.append(dict(rgb=list(rgb), value="#%02X%02X%02X" % rgb,
                           sample_pixels=len(cluster)))
        if len(result) == 2:
            break
    return result


def collect(school, discovery):
    result = dict(school_code=school["school_code"], name_zh=school["name_zh"],
                  checked_at=dt.date.today().isoformat(), status="no_confirmed_homepage", candidates=[], attempts=[])
    if discovery.get("status") != "title_matched":
        return result
    home = discovery["homepage_url"]
    result["page_url"] = home
    policy = Policy()
    try:
        final, data, charset = fetch(home, policy)
        if not same_school(final, home):
            raise ValueError("cross_school_redirect")
        text = data.decode(charset or "utf-8", "replace")
        if "charset=gb" in text[:4000].lower():
            text = data.decode("gb18030", "replace")
        parser = Marks()
        parser.feed(text)
        norm = lambda t: re.sub(r"\s+", "", t).replace("（", "(").replace("）", ")")
        if norm(school["name_zh"]) not in norm(parser.title):
            raise ValueError("homepage_identity_mismatch")
        result["page_title"] = parser.title.strip()[:160]
        images = [(urllib.parse.urljoin(final, src), label) for src, label in parser.images]
        if not images:
            for stylesheet in parser.styles[:2]:
                css = urllib.parse.urljoin(final, stylesheet)
                if not same_school(css, home):
                    continue
                try:
                    css_final, css_bytes, _ = fetch(css, policy, 250_000)
                    for src in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", css_bytes.decode("utf-8", "replace")):
                        if re.search(r"logo|xiaohui|badge", src, re.I):
                            images.append((urllib.parse.urljoin(css_final, src), "stylesheet-linked header mark"))
                except Exception:
                    pass
        unique = {}
        for src, label in images:
            if same_school(src, home) and not re.search(r"\.svg(?:[?#]|$)", src, re.I):
                unique.setdefault(src, label)
        result["status"] = "no_raster_mark_candidate"
        for n, (src, label) in enumerate(list(unique.items())[:3], 1):
            attempt = dict(image_url=src, status="pending")
            result["attempts"].append(attempt)
            try:
                image_final, payload, _ = fetch(src, policy, 3_000_000)
                if not same_school(image_final, home):
                    raise ValueError("cross_school_image_redirect")
                im = Image.open(io.BytesIO(payload))
                width, height = im.size
                if min(width, height) < 20 or width * height > 2_000_000:
                    raise ValueError("not_header_mark_dimensions")
                colors = palette(im)
                if not colors:
                    raise ValueError("no_reliable_chromatic_sample")
                path = TEMP / (school["school_code"] + "-%d.png" % n)
                im.convert("RGBA").save(path)
                result["candidates"].append(dict(image_url=image_final, label=label,
                    width=width, height=height, sha256=hashlib.sha256(payload).hexdigest(),
                    colors=colors, preview_path=str(path.relative_to(ROOT)),
                    method="badge_sample" if re.search(r"校徽|xiaohui|badge", src + label, re.I) else "manual_derived",
                    basis="官网页眉标识图片：滤去透明、近白和低饱和背景后，对高频RGB色簇取通道中位数；不是VI标准色色卡"))
                attempt["status"] = "sampled_candidate"
                result["status"] = "needs_visual_review"
            except Exception as exc:
                attempt.update(status="access_or_sample_gap", error_type=type(exc).__name__, detail=str(exc)[:100])
    except Exception as exc:
        result.update(status="homepage_access_gap", error_type=type(exc).__name__, detail=str(exc)[:100])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    TEMP.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig") as handle:
        schools = list(csv.DictReader(handle))
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(encoding="utf-8-sig") as handle:
        discovery = {r["school_code"]: r for r in csv.DictReader(handle)}
    results = {}
    if args.resume and OUTPUT.exists():
        results = {r["school_code"]: r for r in map(json.loads, OUTPUT.read_text().splitlines())}
    pending = [r for r in schools if r["school_code"] not in results]

    def save():
        temp = OUTPUT.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(results[r["school_code"]], ensure_ascii=False) + "\n"
                                for r in schools if r["school_code"] in results), encoding="utf-8")
        temp.replace(OUTPUT)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect, r, discovery.get(r["school_code"], {})): r["school_code"] for r in pending}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results[futures[future]] = future.result()
            if n % 40 == 0:
                save()
                print(f"Sampled header candidates for {n}/{len(pending)} schools.", flush=True)
    save()
    print(f"Palette candidates: {len(results)} schools; {sum(bool(r['candidates']) for r in results.values())} with samples.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Visit candidate school homepages and collect official page links for review.

Only a homepage whose title contains the complete Ministry school name is
accepted. This does not certify its contents or permission to use resources.
No login, CAPTCHA, or anti-bot bypass is attempted.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import html.parser
import ipaddress
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser


ROOT = pathlib.Path(__file__).resolve().parents[2]
QUEUE = ROOT / "data/review/review-queue-2026.csv"
OUTPUT = ROOT / "data/review/official-page-discovery-2026.csv"
OVERRIDES = ROOT / "data/review/official-site-overrides-2026.csv"
AGENT = "UniversityDesignDB/0.1 (+https://github.com/yangxiake/university-design-db; public-page research)"
TYPES = {
    "overview": ("学校简介", "学校概况", "学校介绍", "学校沿革", "关于学校", "走进"),
    "history": ("历史沿革", "校史沿革", "学校沿革", "校史馆"),
    "visual": ("视觉形象", "学校标识", "校园文化", "形象识别", "标识系统"),
    "templates": ("演示文稿模板", "PPT模板", "ppt模板"),
}


class PageParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.link = None
        self.link_text = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self.link = attrs.get("href")
            self.link_text = []

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.link is not None:
            self.link_text.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "a" and self.link is not None:
            self.links.append(("".join(self.link_text).strip(), self.link))
            self.link = None


def safe_url(url):
    try:
        parsed = urllib.parse.urlparse(url.strip())
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username:
            return False
        if host == "localhost" or host.endswith(".local"):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def site_score(url):
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    return (0 if host.endswith(".edu.cn") else 1,
            0 if host.startswith("www.") or host.count(".") <= 1 else 1,
            0 if parsed.scheme == "https" else 1,
            1 if any(s in host for s in ("english", "en.", "international")) else 0,
            len(parsed.path), len(host))


def normalize_school_name(value):
    return re.sub(r"\s+", "", value).replace("（", "(").replace("）", ")")


def trusted_host(url, override_urls):
    host = urllib.parse.urlparse(url).hostname or ""
    if host.endswith((".edu.cn", ".ac.cn")):
        return True
    return host in {urllib.parse.urlparse(value).hostname for value in override_urls}


def candidate_variants(urls):
    variants = set()
    for url in urls:
        if not safe_url(url):
            continue
        parsed = urllib.parse.urlparse(url)
        variants.add(url)
        if parsed.scheme == "http":
            variants.add(parsed._replace(scheme="https").geturl())
        host = parsed.hostname or ""
        if host.endswith(".edu.cn") and not host.startswith("www."):
            labels = host.split(".")
            if len(labels) == 3:
                variants.add(parsed._replace(scheme="https", netloc="www." + host).geturl())
            elif labels[0] in {"en", "english", "de"}:
                variants.add(parsed._replace(scheme="https", netloc="www." + ".".join(labels[1:])).geturl())
    return sorted((url for url in variants if safe_url(url)), key=site_score)


def allowed_by_robots(url):
    parsed = urllib.parse.urlparse(url)
    robots = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    try:
        request = urllib.request.Request(robots, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(request, timeout=6) as response:
            body = response.read(100_000).decode("utf-8", "ignore")
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.splitlines())
        return parser.can_fetch(AGENT, url)
    except urllib.error.HTTPError as exc:
        return exc.code in {404, 410}
    except OSError:
        return True  # Unknown policy; only one public homepage request follows.


def fetch_page(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=15) as response:
        final_url = response.geturl()
        if not safe_url(final_url):
            raise ValueError("redirected outside public HTTP(S) web")
        mime = response.headers.get_content_type()
        if mime not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("response is not HTML")
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("homepage larger than 2 MB")
        charset = response.headers.get_content_charset()
    for encoding in (charset, "utf-8", "gb18030"):
        if not encoding:
            continue
        try:
            return final_url, payload.decode(encoding)
        except (UnicodeError, LookupError):
            pass
    return final_url, payload.decode("utf-8", "replace")


def page_links(base, links):
    found = {}
    base_host = urllib.parse.urlparse(base).hostname or ""
    labels = base_host.split(".")
    base_domain = ".".join(labels[-3:] if base_host.endswith(".edu.cn") else labels[-2:])
    for kind, terms in TYPES.items():
        matches = []
        for text, href in links:
            compact = re.sub(r"\s+", "", text)
            if not any(term in compact for term in terms):
                continue
            url = urllib.parse.urljoin(base, href)
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            if not safe_url(url) or not (host == base_domain or host.endswith("." + base_domain)):
                continue
            if re.search(r"\.(?:zip|rar|pptx?|docx?|pdf|mp4|mp3|mov|png|jpe?g|gif|svg|webp)(?:$|[?&])",
                         parsed.path + "?" + parsed.query, re.I):
                continue
            rank = next(index for index, term in enumerate(terms) if term in compact)
            matches.append((rank, len(compact), len(url), url))
        found[kind + "_url"] = sorted(matches)[0][3] if matches else ""
    return found


def discover(row, overrides):
    base = {"school_code": row["school_code"], "name_zh": row["name_zh"],
            "priority": row["priority"], "status": "no_candidate",
            "candidate_url": "", "homepage_url": "", "homepage_title": "",
            "overview_url": "", "history_url": "", "visual_url": "", "templates_url": "",
            "checked_at": dt.date.today().isoformat(), "error_type": ""}
    preferred = candidate_variants(overrides.get(row["school_code"], []))
    others = candidate_variants(row["candidate_websites_unverified"].split("|"))
    candidates = preferred + [url for url in others if url not in preferred]
    for url in candidates[:4]:
        base["candidate_url"] = url
        if not allowed_by_robots(url):
            base["status"] = "robots_disallowed"
            continue
        try:
            final_url, content = fetch_page(url)
            parser = PageParser()
            parser.feed(content)
            title = re.sub(r"\s+", "", parser.title)
            base.update(homepage_url=final_url, homepage_title=parser.title.strip()[:200])
            if normalize_school_name(row["name_zh"]) not in normalize_school_name(title):
                base["status"] = "title_mismatch"
                base["error_type"] = ""
                continue
            if not trusted_host(final_url, overrides.get(row["school_code"], [])):
                base["status"] = "site_unverified"
                base["error_type"] = ""
                break
            base["status"] = "title_matched"
            base["error_type"] = ""
            base.update(page_links(final_url, parser.links))
            break
        except Exception as exc:
            base["status"] = "fetch_error"
            base["error_type"] = type(exc).__name__
    return base


def save_results(output, scope_rows, results_by_code):
    """Keep previously collected schools when resuming a selected batch."""
    ordered = [results_by_code[row["school_code"]] for row in scope_rows
               if row["school_code"] in results_by_code]
    if not ordered:
        return
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ordered[0]))
        writer.writeheader()
        writer.writerows(ordered)
    temporary.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority", type=int, choices=[1, 2], default=1)
    parser.add_argument("--limit", type=int, help="Process only this many schools for a small trial")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--resume", action="store_true", help="Keep accepted homepage matches and retry gaps")
    parser.add_argument("--school-code", action="append", help="Restrict updates to selected school codes")
    args = parser.parse_args()
    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        scope_rows = list(csv.DictReader(handle))
    rows = [row for row in scope_rows if int(row["priority"]) <= args.priority]
    if args.school_code:
        rows = [row for row in rows if row["school_code"] in args.school_code]
    overrides = {}
    if OVERRIDES.exists():
        with OVERRIDES.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                overrides.setdefault(row["school_code"], []).append(row["candidate_url"])
    if args.limit:
        rows = rows[:args.limit]
    selected_codes = {row["school_code"] for row in rows}
    prior = {}
    if args.resume and OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8-sig", newline="") as handle:
            prior = {row["school_code"]: row for row in csv.DictReader(handle)}
        for code, item in prior.items():
            if code not in selected_codes:
                continue
            if item["status"] == "title_matched" and not trusted_host(
                    item["homepage_url"], overrides.get(code, [])):
                item["status"] = "site_unverified"
            elif item["status"] == "site_unverified" and trusted_host(
                    item["homepage_url"], overrides.get(code, [])):
                item["status"] = "title_matched"
    results_by_code = dict(prior)
    pending = [row for row in rows if row["school_code"] not in results_by_code or
               results_by_code[row["school_code"]]["status"] not in {
                   "title_matched", "robots_disallowed"} and
               (results_by_code[row["school_code"]]["status"] != "site_unverified" or
                row["school_code"] in overrides)]

    def save():
        save_results(OUTPUT, scope_rows, results_by_code)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(discover, row, overrides): row["school_code"] for row in pending}
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results_by_code[futures[future]] = future.result()
            if completed % 20 == 0:
                save()
                print("Checked %d/%d pending schools." % (completed, len(pending)), flush=True)
    save()
    results = [results_by_code[row["school_code"]] for row in rows]
    counts = {status: sum(row["status"] == status for row in results)
              for status in sorted({row["status"] for row in results})}
    print("Processed %d schools: %r" % (len(results), counts))


if __name__ == "__main__":
    main()

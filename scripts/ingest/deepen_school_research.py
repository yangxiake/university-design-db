#!/usr/bin/env python3
"""Re-read core evidence and public source leads; keep a separate resumable ledger.

This pass validates improved extraction against full pages, not truncated search
snippets. The two ledgers are merged only after collection completes.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

from research_all_schools import ROOT, Policy, read_page, extract_claims, evidence, same_school, classify
from discover_official_pages import safe_url

OUTPUT = ROOT / "data/review/school-research-deeper-2026.jsonl"
PRIOR = ROOT / "data/review/school-research-2026.jsonl"
LEADS = ROOT / "data/review/primary-search-leads-2026.jsonl"


def gather(row, previous, leads, max_pages, skip_sources=()):
    name = row["name_zh"]
    home = previous.get("home")
    result = dict(school_code=row["school_code"], name_zh=name,
                  checked_at=dt.date.today().isoformat(), home=home, pages=[], claims=[],
                  status="needs_source", collector_revision=2)
    candidates = []
    for page in previous.get("pages", []):
        if page.get("status") != "read":
            continue
        source = page.get("source_url", page["requested_url"])
        # A previously visited title can establish a bilingual name without a new request.
        result["claims"].extend(extract_claims(name, page["kind"], page.get("title", ""), "", source))
        if page["kind"] in {"overview", "charter", "history", "culture"}:
            candidates.append((page["kind"], source, "首轮已读取的完整正文复查"))
    for lead in leads:
        source = lead["source_url"]
        if not safe_url(source):
            continue
        title = lead["page_title"]
        host = urllib.parse.urlparse(source).hostname or ""
        if re.search(r"招聘|考察|祝贺|参观|合作|研讨|来校|讲座|新闻|学院\(部\)", title):
            continue
        is_known = home and same_school(source, home)
        is_primary = (host.endswith((".edu.cn", ".gov.cn")) or host == "gaokao.chsi.com.cn") and name in title
        if not is_known and not is_primary:
            continue
        kind = classify(title) or ("charter" if "章程" in title else "overview")
        candidates.append((kind, source, "公开搜索索引线索，读取原页面再判断"))
    rank = {"charter": 0, "overview": 1, "history": 2, "culture": 3, "visual": 4}
    candidates.sort(key=lambda item: (rank.get(item[0], 5), len(item[1])))
    seen = set()
    policy = Policy()
    for kind, url, label in candidates:
        if url in skip_sources:
            continue
        if url in seen:
            continue
        seen.add(url)
        if len(result["pages"]) >= max_pages:
            break
        page = dict(requested_url=url, kind=kind, link_label=label, status="pending")
        result["pages"].append(page)
        if not policy.allowed(url):
            page["status"] = "robots_disallowed"
            continue
        try:
            final, title, text, links, mime, digest = read_page(url, home if home and same_school(url, home) else url)
            if name not in title and name not in text and not home:
                raise ValueError("school_identity_not_in_source")
            page.update(source_url=final, title=title, content_kind=mime, sha256=digest,
                        text_characters=len(text), status="read" if len(text.strip()) >= 60 else "insufficient_text",
                        evidence=evidence(text))
            if page["status"] == "read":
                result["claims"].extend(extract_claims(name, kind, title, text, final))
        except Exception as exc:
            page.update(status="access_limited", error_type=type(exc).__name__, error_detail=str(exc)[:160])
    unique = {json.dumps(c, ensure_ascii=False, sort_keys=True): c for c in result["claims"]}
    result["claims"] = list(unique.values())
    if result["claims"] or any(p["status"] == "read" for p in result["pages"]):
        result["status"] = "researched_partial"
    elif result["pages"]:
        result["status"] = "access_limited"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    parser.add_argument("--retry-gaps", action="store_true", help="Read newly found sources without repeating successful visits")
    args = parser.parse_args()
    output = args.output
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    previous = {r["school_code"]: r for r in (json.loads(l) for l in PRIOR.read_text().splitlines())}
    leads = {}
    if LEADS.exists():
        for line in LEADS.read_text().splitlines():
            item = json.loads(line)
            leads.setdefault(item["school_code"], []).append(item)
    results = {}
    if (args.resume or args.retry_gaps) and output.exists():
        results = {r["school_code"]: r for r in (json.loads(l) for l in output.read_text().splitlines())}
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(encoding="utf-8-sig") as handle:
        discovery = {r["school_code"]: r for r in csv.DictReader(handle)}
    for code, item in previous.items():
        if discovery.get(code, {}).get("status") == "title_matched":
            item["home"] = discovery[code]["homepage_url"]
    successful = {code: {p.get("source_url", p["requested_url"]) for p in item["pages"] if p["status"] == "read"}
                  for code, item in results.items()}
    pending = [r for r in rows if r["school_code"] not in results or args.retry_gaps and
               any(lead["source_url"] not in successful.get(r["school_code"], set()) for lead in leads.get(r["school_code"], []))]

    def save():
        temp = output.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(results[r["school_code"]], ensure_ascii=False) + "\n"
                                for r in rows if r["school_code"] in results), encoding="utf-8")
        temp.replace(output)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(gather, r, previous.get(r["school_code"], {}),
                               leads.get(r["school_code"], []), args.max_pages,
                               successful.get(r["school_code"], set()) if args.retry_gaps else ()): r["school_code"] for r in pending}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            code = futures[future]
            fresh = future.result()
            if args.retry_gaps and code in results:
                old = results[code]
                fresh["pages"] = old["pages"] + fresh["pages"]
                combined = old["claims"] + fresh["claims"]
                fresh["claims"] = list({json.dumps(c, ensure_ascii=False, sort_keys=True): c for c in combined}.values())
                if fresh["claims"] or any(p["status"] == "read" for p in fresh["pages"]):
                    fresh["status"] = "researched_partial"
            results[code] = fresh
            if n % 20 == 0:
                save()
                print(f"Deepened {n}/{len(pending)} schools.", flush=True)
    save()
    print(f"Deeper ledger: {len(results)} schools; {sum(len(r['claims']) for r in results.values())} explicit candidates.")


if __name__ == "__main__":
    main()

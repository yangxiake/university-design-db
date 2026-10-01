#!/usr/bin/env python3
"""Collect bounded school-level badge, flower, mascot and timeline passages.

These passages require interpretation and do not become facts automatically.
Navigation labels and departmental pages are excluded. No media files are saved.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import re

from research_all_schools import ROOT, Policy, read_page, foreign_article

OUTPUT = ROOT / "data/review/narrative-leads-2026.jsonl"


def collect(school, extended=False):
    code, name = school["school_code"], school["name_zh"]
    result = dict(school_code=code, name_zh=name, checked_at=dt.date.today().isoformat(), visits=[], leads=[])
    candidates = {}
    kinds = {"charter", "visual", "history"}
    if extended:
        kinds |= {"overview", "culture", "templates"}
    for p in school["pages"]:
        if p.get("status") == "read" and p["kind"] in kinds:
            bucket = candidates.setdefault(p["kind"], [])
            if len(bucket) < (2 if extended else 1) and p.get("source_url") not in {q.get("source_url") for q in bucket}:
                bucket.append(p)
    policy = Policy()
    for page in [p for bucket in candidates.values() for p in bucket]:
        source = page.get("source_url", page["requested_url"])
        visit = dict(url=source, kind=page["kind"], status="pending")
        result["visits"].append(visit)
        if not policy.allowed(source):
            visit["status"] = "robots_disallowed"
            continue
        try:
            _, title, text, _, _, digest = read_page(source, source)
            if foreign_article(title, name):
                visit["status"] = "foreign_school_article_excluded"
                continue
            remaining = title.replace(name, "学校").replace("学院章程", "")
            if re.search(r"学院|学部|附属", remaining):
                visit["status"] = "department_page_excluded"
                continue
            visit.update(status="read", title=title, sha256=digest)
            sentences = [re.sub(r"\s+", "", s) for s in re.split(r"[\n。！？]", text)]
            used = {}
            budget = 600 if extended else 480
            for sentence in sentences:
                if len(sentence) < 12:
                    continue
                fields = []
                if (re.search(r"(?:校徽|校标|徽志).{0,15}(?:为|是|由|构成|组成|主体|图案|内环|外环)", sentence)
                        and not re.search(r"校旗|旗面|校徽.{0,8}(?:无形资产|知识产权|象征和标志|规范使用)", sentence)
                        and re.search(r"圆形|圆环|同心|图案|主体|造型|构成|组成|字母|篆|盾|外环|内环", sentence)):
                    fields.append("visual.badge_description")
                if re.search(r"校花.{0,5}(?:为|是)|吉祥物.{0,5}(?:为|是)", sentence):
                    fields.append("culture.flower_or_mascot")
                if re.search(r"\d{4}年.{0,50}(?:更名|合并|组建|升格|改建|复校)", sentence):
                    fields.append("culture.history_events")
                if not fields or budget <= 0:
                    continue
                for field in fields:
                    if used.get(field, 0) >= (2 if extended else 1):
                        continue
                    # School history paragraphs may contain more than one date;
                    # retain an explicit truncation marker so they cannot auto-import.
                    excerpt = sentence[:min(200, budget)]
                    result["leads"].append(dict(field=field, source=source, page_title=title,
                                                excerpt=excerpt, truncated=len(excerpt) < len(sentence)))
                    used[field] = used.get(field, 0) + 1
                    budget -= len(excerpt)
        except Exception as exc:
            visit.update(status="access_limited", error_type=type(exc).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--extended", action="store_true", help="Read overview/culture and two pages per relevant kind")
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    schools = [json.loads(l) for l in (ROOT / "data/review/school-research-2026.jsonl").read_text().splitlines()]
    results = {}
    output = args.output
    if args.resume and output.exists():
        results = {r["school_code"]: r for r in (json.loads(l) for l in output.read_text().splitlines())}
    pending = [r for r in schools if r["school_code"] not in results]

    def save():
        temp = output.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(results[r["school_code"]], ensure_ascii=False) + "\n"
                                for r in schools if r["school_code"] in results), encoding="utf-8")
        temp.replace(output)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect, r, args.extended): r["school_code"] for r in pending}
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results[futures[future]] = future.result()
            if n % 40 == 0:
                save()
                print(f"Collected narrative leads for {n}/{len(pending)} schools.", flush=True)
    save()
    print(f"Narrative ledger: {len(results)} schools; {sum(len(r['leads']) for r in results.values())} passages.")


if __name__ == "__main__":
    main()

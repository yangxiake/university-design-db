#!/usr/bin/env python3
"""Research school-owned pages, retaining evidence and access gaps separately.

The output is a resumable research ledger, not a completion certificate. Only
strict scalar claims are eligible for a later import; no pixel/CSS color sampling.
Full HTML, images, PDFs, and template files are never saved in the repository.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html.parser
import io
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from pypdf import PdfReader
import yaml

from discover_official_pages import AGENT, PageParser, safe_url, read_bounded
from extract_official_excerpts import VisibleText
from import_explicit_mottos import candidate_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/review/school-research-2026.jsonl"
TERMS = {
    "overview": ("学校简介", "学校概况", "大学简介", "学校介绍", "学院简介", "学院概况", "学校概览"),
    "charter": ("学校章程", "大学章程", "学院章程", "章程"),
    "visual": ("视觉识别", "视觉形象", "形象识别", "VI设计", "VI系统", "学校标识", "校徽", "校标", "标准色", "大学标识", "学校标志"),
    "culture": ("校训", "校歌", "校花", "吉祥物", "校树", "精神文化", "校园文化"),
    "history": ("历史沿革", "学校沿革", "校史沿革", "建校历程", "办学历史"),
    "templates": ("PPT模板", "ppt模板", "演示文稿模板", "PowerPoint模板"),
    "english": ("English", "ENGLISH", "英文版"),
    "navigation": ("学校概况", "学校概览", "关于学校", "学校文化", "综合信息", "学校历史", "信息公开", "走进"),
}
FACTS = ("identity.name_en", "visual.color_primary", "visual.color_secondary", "visual.vi_url",
         "visual.badge_description", "visual.landmarks", "culture.founded_year", "culture.motto",
         "culture.history_events", "culture.flower", "culture.mascot", "culture.anthem",
         "resources.official_templates_url", "resources.official_template_publisher",
         "resources.official_template_terms")

with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig") as _scope_handle:
    SCHOOL_NAMES = {row["name_zh"] for row in csv.DictReader(_scope_handle)}


def foreign_article(title, name):
    """A school site can repost another university's charter as a reference."""
    heading = re.split(r"\s*[-—|｜]\s*", title)[0]
    normalize = lambda value: value.replace("（", "(").replace("）", ")")
    heading = normalize(heading)
    own = normalize(name)
    # A longer institution name can contain this school's full name, e.g.
    # 中国矿业大学 and 中国矿业大学(北京); substring matching conflates them.
    if any(own in normalize(other) and normalize(other) in heading
           for other in SCHOOL_NAMES if other != name):
        return True
    return own not in heading and any(
        normalize(other) in heading for other in SCHOOL_NAMES if other != name)


def domain(url):
    host = urllib.parse.urlparse(url).hostname or ""
    return ".".join(host.split(".")[-3 if host.endswith((".edu.cn", ".ac.cn")) else -2:])


def same_school(url, home):
    host = urllib.parse.urlparse(url).hostname or ""
    base = domain(home)
    return safe_url(url) and (host == base or host.endswith("." + base))


class Policy:
    def __init__(self):
        self.cache = {}

    def allowed(self, url):
        parsed = urllib.parse.urlparse(url)
        origin = parsed.scheme + "://" + parsed.netloc
        if origin not in self.cache:
            try:
                request = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": AGENT})
                with urllib.request.urlopen(request, timeout=6) as response:
                    body = read_bounded(response,100_000,10).decode("utf-8", "ignore")
                policy = urllib.robotparser.RobotFileParser()
                policy.parse(body.splitlines())
                self.cache[origin] = policy
            except urllib.error.HTTPError as exc:
                self.cache[origin] = exc.code in {404, 410}
            except ValueError:
                self.cache[origin] = False
            except OSError:
                self.cache[origin] = True
        policy = self.cache[origin]
        return policy if isinstance(policy, bool) else policy.can_fetch(AGENT, url)


def classify(label):
    label = re.sub(r"\s+", "", label)
    for kind, terms in TERMS.items():
        if any(term in label for term in terms):
            return kind
    return None


def links_for(base, links, home):
    result = []
    for label, href in links:
        kind = classify(label)
        url = urllib.parse.urljoin(base, href).split("#")[0]
        if not kind or not same_school(url, home):
            continue
        if re.search(r"\.(?:zip|rar|pptx?|docx?|mp4|mp3|mov|png|jpe?g|gif|svg|webp)$", urllib.parse.urlparse(url).path, re.I):
            continue
        result.append((kind, url, label[:60]))
    return sorted(set(result), key=lambda item: (list(TERMS).index(item[0]), len(item[2]), len(item[1])))


def read_page(url, home):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/pdf"})
    with urllib.request.urlopen(request, timeout=15) as response:
        final = response.geturl()
        if not same_school(final, home):
            raise ValueError("cross_school_redirect")
        mime = response.headers.get_content_type()
        payload = read_bounded(response,5_000_000)
        if len(payload) > 5_000_000:
            raise ValueError("document_size_limit")
        charset = response.headers.get_content_charset()
    digest = hashlib.sha256(payload).hexdigest()
    if mime == "application/pdf" or payload.startswith(b"%PDF"):
        reader = PdfReader(io.BytesIO(payload))
        if len(reader.pages) > 40:
            raise ValueError("pdf_page_limit")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return final, "", text, [], "pdf", digest
    if mime not in {"text/html", "application/xhtml+xml"}:
        raise ValueError("unsupported_content_type")
    content = None
    for encoding in (charset, "utf-8", "gb18030"):
        if not encoding:
            continue
        try:
            content = payload.decode(encoding)
            break
        except (UnicodeError, LookupError):
            pass
    if content is None:
        content = payload.decode("utf-8", "replace")
    visible = VisibleText()
    visible.feed(content)
    navigation = PageParser()
    navigation.feed(content)
    text = re.sub(r"[ \t\r\u3000]+", " ", "".join(visible.parts))
    text = re.sub(r"\n\s*\n", "\n", text)
    return final, visible.title.strip()[:200], text, navigation.links, "html", digest


def extract_claims(name, kind, title, text, source):
    """Narrow assertions. Ambiguous prose remains a short lead, never a fact."""
    compact = re.sub(r"\s+", "", text)
    claims = []
    if foreign_article(title, name):
        return claims
    remaining_title = title.replace(name, "学校")
    for heading in ("学院简介", "学院概况", "学院章程"):
        remaining_title = remaining_title.replace(heading, "")
    if re.search(r"学院|学部|附属|中学|小学", remaining_title):
        return claims

    def add(field, value, basis=None):
        if value is None or value == "":
            return
        item = {"field": field, "value": value, "source": source}
        if basis:
            item["basis"] = basis
        if item not in claims:
            claims.append(item)

    institution_page = kind in {"overview", "charter", "history", "culture", "visual", "homepage"}
    if institution_page:
        if name in title:
            bilingual = re.search(r"(?:\||[-—])\s*([A-Za-z][A-Za-z ,()&.'’\-]{5,100})$", title)
            if bilingual and re.search(r"University|College|Institute|Academy", bilingual.group(1), re.I):
                add("identity.name_en", bilingual.group(1).strip(), "官网双语页标题明确同时列出本校中文名与英文名")
        for sentence in re.split(r"[\n。！？]", text):
            sentence = sentence.strip()
            # Avoid a motto merely quoted in a speech or another institution's name.
            current_subject = (name in sentence or re.search(r"(?:学校|本校)[^。；]{0,50}校训",sentence) or
                               re.match(r"(?:第[一二三四五六七八九十百\d]+条\s*)?校训",sentence))
            historical = re.search(r"前身|曾用校训|原校训|旧校训|时期的校训",sentence)
            if "校训" in sentence and current_subject and not historical and len(sentence) < 600 and not re.search(r"中学|小学|附属|学院校训|大学校训", sentence.replace(name, "学校")):
                for value in candidate_values(sentence):
                    if re.fullmatch(r"[\u4e00-\u9fff，、；,; ·]{4,28}", value):
                        add("culture.motto", value)
        for match in re.finditer(r"(?:学校|本校|" + re.escape(name) + r")(?:的)?校训(?:是|为|：|:)[“\"]?([\u4e00-\u9fff，、；,;·]{4,24})", compact):
            value = match.group(1).rstrip("，、；,;")
            # An item followed by a colon is an explanation heading, not the full motto.
            following = compact[match.end():match.end() + 1]
            if following not in {"：", ":"} and not re.search(r"坚持|秉承|精神|以及|学校|践行|不断", value):
                add("culture.motto", value)
        for match in re.finditer(r"(?:学校|本校|" + re.escape(name) + r")(?:的)?(?:英文名称|英文校名)(?:为|是|：|:)\s*[“\"]?([A-Za-z][A-Za-z ,()&.'’\-]{5,110})", text):
            value = match.group(1).strip().rstrip(" ,.")
            if re.search(r"University|College|Institute|Academy", value, re.I):
                add("identity.name_en", value)
        for match in re.finditer(r"英文(?:名称|校名|全称)(?:为|是|：|:)\s*[“\"]?([A-Za-z][A-Za-z ,()&.'’\-]{5,110})", text):
            preceding = text[max(0, match.start() - 160):match.start()]
            if name in re.sub(r"\s+", "", preceding) or re.search(r"学校(?:名称|中文名称|全称)", preceding):
                value = match.group(1).strip().rstrip(" ,.")
                if re.search(r"University|College|Institute|Academy", value, re.I):
                    add("identity.name_en", value)
        for key, keyword in (("flower", "校花"), ("mascot", "吉祥物")):
            for match in re.finditer(r"(?:学校|本校|" + re.escape(name) + r")(?:的)?" + keyword + r"(?:为|是|：|:)[“\"]([^”\"。；]{1,16})[”\"]", compact):
                add("culture." + key, match.group(1))
        for match in re.finditer(r"(?:学校|本校|" + re.escape(name) + r")(?:的)?校歌(?:为|是|：|:)《([^》]{1,30})》", compact):
            add("culture.anthem", "《" + match.group(1) + "》")
    if kind in {"overview", "charter", "history"}:
        for raw_sentence in re.split(r"[\n。！？]", text):
            sentence = re.sub(r"\s+", "", raw_sentence).lstrip("\ufeff")
            subject = r"(?:学校|本校|" + re.escape(name) + (r"|学院" if name.endswith("学院") else "") + r")"
            prefix = r"^(?:第[一二三四五六七八九十百零0-9]+条)?"
            direct = re.search(prefix + subject + r"(?:于)?(?:(\d{4})年)?(始建|创建|创办|建校|创立|成立)(?:于)?(?:(\d{4})年)?", sentence)
            if direct and (direct.group(1) or direct.group(3)):
                year = int(direct.group(1) or direct.group(3))
                if 1000 <= year <= dt.date.today().year:
                    add("culture.founded_year", year, f"官网{kind}页直接记载学校{direct.group(2)}年份；未将更名年份或院系年份当作建校年")
            descriptive = re.search(prefix + subject + r"([^。；\d]{1,80}?)(始建|创建|创办|建校|创立|成立)(?:于)?(\d{4})年", sentence)
            if descriptive:
                intervening = re.sub(r"[（(](?:简称|以下简称)[‘’“\"]?学校[’‘”\"]?[）)]", "", descriptive.group(1))
                if not re.search(r"前身|附属|学院|学校|分校|研究|学科|系|追溯|合并|由", intervening):
                    year = int(descriptive.group(3))
                    if 1000 <= year <= dt.date.today().year:
                        add("culture.founded_year", year,
                            f"官网{kind}以本校为主语，描述所在地或性质后明确记载{descriptive.group(2)}年份；未采用前身或院系的年份")
            origin = re.search(prefix + subject + r"(?:的)?(?:前身(?:是|为)|办学历史(?:可|可以)?(?:追溯|上溯|溯源|源)(?:到|至|于))[^。；]{0,35}?(\d{4})年", sentence)
            if origin:
                year = int(origin.group(1))
                if 1000 <= year <= dt.date.today().year:
                    add("culture.founded_year", year, "官网将办学历史起点追溯至该年或明确记载该年前身；口径为前身起源，不等于现名或独立设置年份")
    if kind == "visual" and re.search(r"标识|识别|VI设计|VI系统|校徽|校标", title):
        if not re.search(r"学院|学部|系", title.replace(name, "学校")):
            add("visual.vi_url", source)
    # Colors, historical events and landmarks require contextual interpretation.
    return claims


def evidence(text):
    snippets = []
    for sentence in re.split(r"[\n。！？]", text):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if re.search(r"校训|始建|创办|创立|办学历史|英文名称|标准色|RGB|HEX|校徽|校花|吉祥物|校歌|PPT模板|演示文稿模板", sentence, re.I):
            snippets.append(sentence[:70])
        if len(snippets) >= 4:
            break
    return snippets


def research(row, discovery, max_pages):
    code = row["school_code"]
    profile_path = ROOT / "universities" / row["province"] / code / "profile.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else None
    item = discovery.get(code, {})
    home = item.get("homepage_url") if item.get("status") == "title_matched" else None
    if not home and profile:
        fact = profile["identity"]["official_website"]
        if fact["availability"] == "found":
            home = fact["value"]
    result = {"school_code": code, "name_zh": row["name_zh"], "checked_at": dt.date.today().isoformat(),
              "homepage_discovery_status": item.get("status", "no_candidate"), "home": home,
              "pages": [], "document_leads": [], "claims": [], "field_audit": {},
              "status": "needs_source", "page_budget": max_pages}
    if not home:
        if item.get("candidate_url"):
            result["pages"].append({"requested_url": item["candidate_url"], "kind": "homepage",
                                    "status": item.get("status"), "error_type": item.get("error_type", "")})
        result["field_audit"] = {field: "source_not_confirmed" for field in FACTS}
        return result
    pending = [("homepage", home, "官网首页")]
    for kind in ("overview", "history", "visual", "templates"):
        if item.get(kind + "_url") and same_school(item[kind + "_url"], home):
            pending.append((kind, item[kind + "_url"], "首页已发现入口"))
    if profile:
        for group, key, kind in (("visual", "vi_url", "visual"), ("resources", "official_templates_url", "templates")):
            fact = profile[group][key]
            if fact["availability"] == "found" and same_school(fact["value"], home):
                pending.append((kind, fact["value"], "已有档案入口"))
    policy = Policy()
    seen = set()
    attempted_by_kind = {}
    while pending and len(result["pages"]) < max_pages:
        kind, url, label = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if attempted_by_kind.get(kind, 0) >= (3 if kind in {"overview", "visual", "charter"} else 2):
            continue
        attempted_by_kind[kind] = attempted_by_kind.get(kind, 0) + 1
        page = {"requested_url": url, "kind": kind, "link_label": label, "status": "pending"}
        result["pages"].append(page)
        if not policy.allowed(url):
            page["status"] = "robots_disallowed"
            continue
        try:
            final, title, text, links, mime, digest = read_page(url, home)
            page.update(source_url=final, title=title, content_kind=mime, sha256=digest,
                        text_characters=len(text), status="read" if len(text.strip()) >= 60 else "insufficient_text")
            page["evidence"] = evidence(text)
            if page["status"] != "read":
                continue
            claims = extract_claims(row["name_zh"], kind, title, text, final)
            result["claims"].extend(claim for claim in claims if claim not in result["claims"])
            new_links = links_for(final, links, home)
            for link in new_links:
                if re.search(r"\.pdf$", urllib.parse.urlparse(link[1]).path, re.I):
                    result["document_leads"].append({"kind": link[0], "url": link[1], "label": link[2], "source": final})
            # Fair distribution of requests across page kinds before second/third pages.
            pending.extend(link for link in new_links if link[1] not in seen)
            pending.sort(key=lambda link: (attempted_by_kind.get(link[0], 0), list(TERMS).index(link[0]) if link[0] in TERMS else -1))
        except Exception as exc:
            page.update(status="access_limited", error_type=type(exc).__name__,
                        error_detail=str(exc)[:160])
    good = [page for page in result["pages"] if page["status"] == "read"]
    result["status"] = "researched_partial" if good else "access_limited"
    for field in FACTS:
        if any(claim["field"] == field for claim in result["claims"]):
            result["field_audit"][field] = "explicit_candidate"
        elif good:
            result["field_audit"][field] = "no_explicit_claim_in_visited_pages"
        else:
            result["field_audit"][field] = "access_limited"
    result["navigation_exhausted"] = not pending
    return result


def save(rows, results):
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            if row["school_code"] in results:
                handle.write(json.dumps(results[row["school_code"]], ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-gaps", action="store_true", help="Retry prior access gaps when new confirmed URLs are available")
    parser.add_argument("--school-code", action="append")
    args = parser.parse_args()
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        discovery = {row["school_code"]: row for row in csv.DictReader(handle)}
    results = {}
    if OUTPUT.exists():
        results = {item["school_code"]: item for item in (json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines())}
    pending = [row for row in rows if (not args.school_code or row["school_code"] in args.school_code)
               and (not args.resume or row["school_code"] not in results or args.retry_gaps and
                    discovery.get(row['school_code'],{}).get('status')=='title_matched' and
                    (results[row['school_code']].get('status') in {'needs_source','access_limited'} or
                     results[row['school_code']].get('home')!=discovery[row['school_code']]['homepage_url']))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(research, row, discovery, args.max_pages): row["school_code"] for row in pending}
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            code=futures[future]; fresh=future.result()
            if args.retry_gaps and code in results:
                from merge_research_passes import merge
                results[code]=merge(results[code],fresh,discovery.get(code,{}))
            else:
                results[code]=fresh
            if completed % 20 == 0:
                save(rows, results)
                print(f"Researched {completed}/{len(pending)} schools; ledger has {len(results)} schools.", flush=True)
    save(rows, results)
    print(f"Ledger: {len(results)} schools, {sum(len(item['pages']) for item in results.values())} page visits, "
          f"{sum(len(item['claims']) for item in results.values())} explicit candidates.")


if __name__ == "__main__":
    main()

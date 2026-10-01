#!/usr/bin/env python3
"""Generate school and field-level audit queues without declaring completion."""
import collections
import csv
import json
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
KINDS = {
    "identity.name_en": {"homepage", "overview", "charter", "english"},
    "visual.color_primary": {"visual", "charter"}, "visual.color_secondary": {"visual", "charter"},
    "visual.vi_url": {"visual", "homepage"}, "visual.badge_description": {"visual", "charter"},
    "visual.landmarks": {"visual", "culture", "navigation"},
    "culture.founded_year": {"overview", "history", "charter"}, "culture.motto": {"overview", "culture", "charter", "visual"},
    "culture.history_events": {"overview", "history", "charter"},
    "culture.flower": {"culture", "charter"}, "culture.mascot": {"culture", "charter"},
    "culture.anthem": {"culture", "charter"},
    "resources.official_templates_url": {"templates", "visual"},
    "resources.official_template_publisher": {"templates"}, "resources.official_template_terms": {"templates"},
}


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    ledger = {item["school_code"]: item for item in (json.loads(line) for line in
              (ROOT / "data/review/school-research-2026.jsonl").read_text(encoding="utf-8").splitlines())}
    schools = []
    fields = []
    visits = []
    for row in scope:
        item = ledger.get(row["school_code"])
        path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
        profile = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
        pages = item["pages"] if item else []
        schools.append(dict(school_code=row["school_code"], name_zh=row["name_zh"], province=row["province"],
                            collection_status=item["status"] if item else "not_started",
                            attempted_pages=len(pages), read_pages=sum(p["status"] == "read" for p in pages),
                            access_gaps=sum(p["status"] != "read" for p in pages),
                            explicit_candidates=len(item["claims"]) if item else 0,
                            checked_at=item["checked_at"] if item else "",
                            profile_path=str(path.relative_to(ROOT)) if path.exists() else ""))
        for page in pages:
            visits.append(dict(school_code=row["school_code"], name_zh=row["name_zh"], kind=page["kind"],
                               requested_url=page["requested_url"], source_url=page.get("source_url", ""),
                               status=page["status"], title=page.get("title", ""),
                               checked_at=item["checked_at"], error_type=page.get("error_type", "")))
        for field, relevant in KINDS.items():
            group, key = field.split(".")
            fact = profile[group][key] if profile else None
            recorded = isinstance(fact, dict) and fact.get("availability") != "unresearched" or isinstance(fact, list) and bool(fact)
            evidence_pages = [p for p in pages if p["kind"] in relevant and p["status"] == "read"]
            if recorded:
                state = fact["availability"] if isinstance(fact, dict) else "found"
                next_action = "保持来源及版本，处理差异并继续补采缺项；人工核验可后续进行"
            elif evidence_pages:
                state = "needs_interpretation"
                next_action = "继续阅读原页、图表或手册并检索该字段；自动规则未提取不等于资料不存在"
            elif pages and all(p["status"] != "read" for p in pages):
                state = "access_limited"
                next_action = "使用其他公开有效来源或在可访问环境读取官网；不可据此认定字段不存在"
            else:
                state = "needs_source"
                next_action = "寻找该字段的校级来源入口；仅首页访问不能完成该字段调查"
            sources = []
            if isinstance(fact, dict):
                sources += [fact.get("source")] + fact.get("search_sources", [])
                sources += [c.get("source") for c in fact.get("candidates", [])]
            elif isinstance(fact, list):
                sources += [entry.get("source") for entry in fact]
            sources += [p.get("source_url", p["requested_url"]) for p in evidence_pages]
            fields.append(dict(school_code=row["school_code"], name_zh=row["name_zh"], field=field,
                               state=state, source_urls="|".join(dict.fromkeys(s for s in sources if s)),
                               checked_at=item["checked_at"] if item else "", next_action=next_action))
    write_csv(ROOT / "data/review/school-research-status-2026.csv", schools, list(schools[0]))
    write_csv(ROOT / "data/review/field-research-status-2026.csv", fields, list(fields[0]))
    write_csv(ROOT / "data/review/page-visits-2026.csv", visits,
              ["school_code", "name_zh", "kind", "requested_url", "source_url", "status", "title", "checked_at", "error_type"])
    counts = collections.Counter(item["collection_status"] for item in schools)
    states = collections.Counter(item["state"] for item in fields)
    lines = ["# 1412 所逐校访查记录", "", "本表统计访问和自动提取进度，不等于资料补齐或人工签核。", "",
             f"范围：{len(scope)} 所；访查台账：{len(ledger)} 所；尝试读取页面：{len(visits)} 个。", "",
             "| 调查状态 | 学校数 |", "| --- | ---: |"]
    labels = {"researched_partial": "已读取部分校方资料，仍有字段缺口", "access_limited": "已有官网入口，本次读取受限",
              "needs_source": "尚需确认可用校方来源", "not_started": "尚未进入本轮台账"}
    lines.extend(f"| {labels.get(key, key)} | {value} |" for key, value in sorted(counts.items()))
    lines.extend(["", "| 字段状态 | 条数 |", "| --- | ---: |"])
    lines.extend(f"| {key} | {value} |" for key, value in sorted(states.items()))
    lines.extend(["", "逐校台账：[学校状态](../data/review/school-research-status-2026.csv)、"
                  "[逐字段待办](../data/review/field-research-status-2026.csv)、"
                  "[页面访问记录](../data/review/page-visits-2026.csv)。", "",
                  "颜色的图片标注、校徽释义、历史口径和模板条款需要进一步判读；"
                  "`needs_interpretation` 与 `needs_source` 均表示未完成。"
                  "网站禁止访问、失败或没有可提取文本，也不表示该校缺少相关材料。", ""])
    (ROOT / "docs/research-progress-2026.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Research report: {counts}; field states: {states}")


if __name__ == "__main__":
    main()

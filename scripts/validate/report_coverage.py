#!/usr/bin/env python3
"""Create a transparent coverage report; profile count is not research coverage."""

import collections
import csv
import pathlib

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIELDS = {
    "visual.color_primary": ("visual", "color_primary"),
    "culture.founded_year": ("culture", "founded_year"),
    "culture.motto": ("culture", "motto"),
    "resources.official_templates_url": ("resources", "official_templates_url"),
    "resources.official_template_terms": ("resources", "official_template_terms"),
}


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    statuses = collections.Counter()
    fields = {key: collections.Counter() for key in FIELDS}
    reviewer_count = 0
    ready = 0
    profile_count = 0
    for row in scope:
        path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
        if not path.exists():
            statuses["unresearched"] += 1
            for counts in fields.values():
                counts["unresearched"] += 1
            continue
        profile_count += 1
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        statuses[profile["research"]["status"]] += 1
        if profile["research"]["status"] == "reviewed":
            reviewer_count += 1
        for label, (group, key) in FIELDS.items():
            fact = profile[group][key]
            fields[label][fact["availability"]] += 1
            if fact["availability"] == "found":
                fields[label]["found_" + fact["verified"]] += 1
        color = profile["visual"]["color_primary"]
        year = profile["culture"]["founded_year"]
        if (color["availability"] == year["availability"] == "found"
                and color["verified"] == year["verified"] == "human"):
            ready += 1
    out = ROOT / "docs/coverage-2026.md"
    lines = ["# 2026 年资料覆盖率", "",
             "自动生成报告。933 是纳入范围与档案目录数量，不是调查完成数。", "",
             f"- 范围学校：{len(scope)}",
             f"- 已建单校档案：{profile_count}",
             f"- 尚未建档：{len(scope) - profile_count}",
             f"- 已人工签核档案：{reviewer_count}",
             f"- 主色和建校年均已人工确认的档案：{ready}", "",
             "## 调查状态", "",
             "| 状态 | 学校数 |", "| --- | ---: |"]
    for status in ("unresearched", "in_progress", "needs_review", "reviewed"):
        lines.append(f"| {status} | {statuses[status]} |")
    lines += ["", "## 关键字段", "",
              "| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label, counts in fields.items():
        lines.append("| %s | %d | %d | %d | %d | %d |" % (
            label, counts["unresearched"], counts["found_auto"],
            counts["found_human"], counts["not_found"], counts["conflict"]))
    candidate_path = ROOT / "data/review/wikidata-candidates-2026.csv"
    if candidate_path.exists():
        with candidate_path.open(encoding="utf-8-sig", newline="") as handle:
            candidate_rows = list(csv.DictReader(handle))
        candidate_statuses = collections.Counter(r["match_status"] for r in candidate_rows)
        lines += ["", "## 自动检索候选（仅供复核）", "",
                  "Wikidata 匹配及网站、建校年均是候选线索，未写入学校事实字段。", "",
                  "| 匹配状态 | 学校数 |", "| --- | ---: |"]
        for status, count in sorted(candidate_statuses.items()):
            lines.append(f"| {status} | {count} |")
        gap_path = ROOT / "data/review/wikidata-search-gaps-2026.csv"
        if gap_path.exists():
            with gap_path.open(encoding="utf-8-sig", newline="") as handle:
                gap_rows = list(csv.DictReader(handle))
            gap_statuses = collections.Counter(r["status"] for r in gap_rows)
            lines += ["", "未取得唯一准确匹配的 32 所又尝试 API 搜索；搜索结果仍需辨认学校身份。",
                      f"取得搜索候选 {gap_statuses['search_results']} 所；无结果 {gap_statuses['no_search_results']} 所；接口请求失败 {sum(count for status, count in gap_statuses.items() if status.startswith('request_error'))} 所。"]
    lines += ["", "## 发布判断", "",
              "正式公开版本要求 933 所逐校完成调查与人工复核，并通过 `validate_profiles.py --release`。",
              "本报告只记录当前数量，不替代逐条来源复核。", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()

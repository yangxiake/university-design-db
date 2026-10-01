#!/usr/bin/env python3
"""Create a transparent coverage report; profile count is not research coverage."""

import collections
import csv
import pathlib

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIELDS = {
    "identity.name_en": ("identity", "name_en"),
    "identity.official_website": ("identity", "official_website"),
    "visual.color_primary": ("visual", "color_primary"),
    "visual.color_secondary": ("visual", "color_secondary"),
    "visual.vi_url": ("visual", "vi_url"),
    "visual.badge_description": ("visual", "badge_description"),
    "culture.founded_year": ("culture", "founded_year"),
    "culture.motto": ("culture", "motto"),
    "culture.flower": ("culture", "flower"),
    "culture.mascot": ("culture", "mascot"),
    "culture.anthem": ("culture", "anthem"),
    "resources.official_templates_url": ("resources", "official_templates_url"),
    "resources.official_template_publisher": ("resources", "official_template_publisher"),
    "resources.official_template_terms": ("resources", "official_template_terms"),
}


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    statuses = collections.Counter()
    fields = {key: collections.Counter() for key in FIELDS}
    priority_fields = {key: collections.Counter() for key in FIELDS}
    priority_profiles = 0
    priority_count = 0
    reviewer_count = 0
    ready = 0
    auto_design_basis = 0
    profile_count = 0
    lists = {"culture.history_events": collections.Counter(), "visual.landmarks": collections.Counter()}
    color_methods = collections.Counter()
    community = collections.Counter()
    for row in scope:
        is_priority = "double_first" in row["scope_tags"].split("|")
        priority_count += is_priority
        path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
        if not path.exists():
            statuses["unresearched"] += 1
            for counts in fields.values():
                counts["unresearched"] += 1
            if is_priority:
                for counts in priority_fields.values():
                    counts["unresearched"] += 1
            continue
        profile_count += 1
        priority_profiles += is_priority
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        for label, counts in lists.items():
            group, key = label.split(".")
            entries = profile[group][key]
            counts["schools"] += bool(entries)
            counts["entries"] += len(entries)
            counts["human"] += sum(e["verified"] == "human" for e in entries)
        items = profile['resources'].get('community_resources', [])
        community['schools'] += bool(items)
        community['entries'] += len(items)
        community.update(item['kind'] for item in items)
        for group, key in FIELDS.values():
            if profile[group][key].get('source_type') == 'community_dataset':
                community['dataset_facts'] += 1
        primary = profile["visual"]["color_primary"]
        if primary["availability"] == "found":
            color_methods[primary["method"]] += 1
        statuses[profile["research"]["status"]] += 1
        if profile["research"]["status"] == "reviewed":
            reviewer_count += 1
        for label, (group, key) in FIELDS.items():
            fact = profile[group][key]
            fields[label][fact["availability"]] += 1
            if fact["availability"] == "found":
                fields[label]["found_" + fact["verified"]] += 1
            if is_priority:
                priority_fields[label][fact["availability"]] += 1
                if fact["availability"] == "found":
                    priority_fields[label]["found_" + fact["verified"]] += 1
        color = profile["visual"]["color_primary"]
        year = profile["culture"]["founded_year"]
        auto_design_basis += color["availability"] == year["availability"] == "found"
        if (color["availability"] == year["availability"] == "found"
                and color["verified"] == year["verified"] == "human"):
            ready += 1
    out = ROOT / "docs/coverage-2026.md"
    lines = ["# 2026 年资料覆盖率", "",
             "自动生成报告。1412 是纳入范围数量，不是调查完成数或档案数。", "",
             f"- 范围学校：{len(scope)}",
             f"- 已建单校档案：{profile_count}",
             f"- 尚未建档：{len(scope) - profile_count}",
             f"- 已有附来源主色与建校年的档案：{auto_design_basis}（含自动采集与建议色，不表示所有字段完备）",
             f"- 已人工签核档案：{reviewer_count}",
             f"- 主色和建校年均已人工确认的档案：{ready}", "",
             "## 调查状态", "",
             "| 状态 | 学校数 |", "| --- | ---: |"]
    for status in ("unresearched", "in_progress", "auto_collected", "needs_review", "reviewed"):
        lines.append(f"| {status} | {statuses[status]} |")
    lines += ["", "## 关键字段", "",
              "| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label, counts in fields.items():
        lines.append("| %s | %d | %d | %d | %d | %d |" % (
            label, counts["unresearched"], counts["found_auto"],
            counts["found_human"], counts["not_found"], counts["conflict"]))
    lines += ["", "## 首批双一流档案", "",
              f"剔除三所军校后共 {priority_count} 所；已开始建档 {priority_profiles} 所。建档不表示单校资料齐全。", "",
              "| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label, counts in priority_fields.items():
        lines.append("| %s | %d | %d | %d | %d | %d |" % (
            label, counts["unresearched"], counts["found_auto"],
            counts["found_human"], counts["not_found"], counts["conflict"]))
    lines += ["", "## 校史与校园地标", "",
              "条目是有来源的校史节点节选及地标名称，不表示完整校史或完整校园清单。", "",
              "| 字段 | 有资料学校 | 条目数 | 人工确认条目 |", "| --- | ---: | ---: | ---: |"]
    for label, counts in lists.items():
        lines.append(f"| {label} | {counts['schools']} | {counts['entries']} | {counts['human']} |")
    lines += ["", "## 主色取值方法", "",
              "关键字段中的主色已找到数量包含两类资料：学校公布的数字标准色，以及本库标注用途的PPT建议色。建议色不等于官方VI标准色。", "",
              "| 方法 | 学校数 | 含义 |", "| --- | ---: | --- |"]
    for method, label in [("official_vi", "学校发布的RGB/HEX标准值"),
                          ("badge_sample", "校徽像素取样，PPT建议色"),
                          ("manual_derived", "官网标识取色或人工推导，PPT建议色")]:
        lines.append(f"| {method} | {color_methods[method]} | {label} |")
    lines += ['', '## 社区资料', '',
              f"- 已匹配社区资源学校：{community['schools']}",
              f"- 资源入口条目：{community['entries']}",
              f"- 其中Beamer主题：{community['beamer_theme']}；Marp主题：{community['marp_theme']}；校徽参考：{community['logo_reference']}；校史参考：{community['history_reference']}",
              f"- 社区数据补充的事实：{community['dataset_facts']}（已计入关键字段，非校方现行声明）", '',
              '资源索引见indexes/community-resources.csv。社区配色不计入学校主题色统计。']
    enriched_path=ROOT/'data/review/enriched-coverage-2026.json'
    if enriched_path.exists():
        import json
        enriched=json.loads(enriched_path.read_text())['counts']
        lines += ['', '## v3字段并集与视觉文件', '',
                  f"- 逐文件校徽/校名资源：{enriched['logo_schools']}所、{enriched['logo_entries']}条",
                  f"- 结构化配色：{enriched['palette_schools']}所、{enriched['palette_entries']}条（包含建议色，不等于官方标准覆盖）",
                  f"- 历史排名：{enriched['ranking_schools']}所、{enriched['ranking_entries']}条",
                  f"- 学科评估节选：{enriched['subject_schools']}所、{enriched['subject_entries']}条",
                  f"- 重庆2025社区录取参考：{enriched['admission_schools']}所、{enriched['admission_entries']}条",
                  '', '新增27个事实字段和12个集合的逐项填充及上游字段落点见[字段并集报告](github-field-union-2026.md)。']
    official_path=ROOT/'data/review/official-extension-coverage-2026.json'
    if official_path.exists():
        import json
        official=json.loads(official_path.read_text())
        counts=official['current_facts']
        lines+=['','## 官网联系与门户补采','',
                '| 字段 | 有来源学校数 |','| --- | ---: |']
        for field in ('institution.nature','location.address','location.postal_code','contacts.phone','contacts.email','resources.admissions_url','resources.information_disclosure_url','resources.english_website'):
            lines.append('| %s | %s |'%(field,counts.get(field,0)))
        lines+=['','字段保存原标签、短证据与口径；门户是官网导航链接。实际访问状态、官网标识文件与取色覆盖见[官网扩展报告](official-extension-progress-2026.md)。']
    overrides_path=ROOT/'data/review/official-site-overrides-2026.csv'
    if overrides_path.exists():
        with overrides_path.open(encoding='utf-8-sig',newline='') as handle:
            overrides=list(csv.DictReader(handle))
        lines += ['', '## 附来源网址候选', '',
                  f"- 已有附来源入口线索的学校：{len({r['school_code'] for r in overrides if r['evidence_url']})}",
                  '候选不等于已确认官网。未确认时可在单校research.website_candidates中查看。']
    discovery_path = ROOT / "data/review/official-page-discovery-2026.csv"
    if discovery_path.exists():
        with discovery_path.open(encoding="utf-8-sig", newline="") as handle:
            discoveries = list(csv.DictReader(handle))
        discovery_statuses = collections.Counter(r["status"] for r in discoveries)
        lines += ["", "## 官网页面发现", "",
                  "从候选网址访问公开首页；标题包含教育部校名且域名通过筛选才记为 `title_matched`。此步骤是自动判断。", "",
                  f"- 已处理学校：{len(discoveries)}",
                  f"- 无候选网址：{discovery_statuses['no_candidate']}",
                  f"- 首页标题匹配：{discovery_statuses['title_matched']}",
                  f"- 标题匹配但站点归属待核对：{discovery_statuses['site_unverified']}",
                  f"- 找到概况页候选：{sum(bool(r['overview_url']) for r in discoveries)}",
                  f"- 访问或识别未完成：{len(discoveries) - discovery_statuses['title_matched']}"]
        excerpt_path = ROOT / "data/review/official-excerpts-2026.csv"
        if excerpt_path.exists():
            with excerpt_path.open(encoding="utf-8-sig", newline="") as handle:
                excerpts = list(csv.DictReader(handle))
            lines += [f"- 官网短证据候选：{sum(r['status'] == 'candidate' for r in excerpts)}（含需要排除的误匹配，不等于已录事实）"]
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
            lines += ["", "历史补查表对当时未取得唯一准确匹配的学校尝试API搜索；不代表本轮全量本科缺口。",
                      f"取得搜索候选 {gap_statuses['search_results']} 所；无结果 {gap_statuses['no_search_results']} 所；接口请求失败 {sum(count for status, count in gap_statuses.items() if status.startswith('request_error'))} 所。"]
    lines += ["", "## 发布判断", "",
              "本轮采用自动采集版：不要求人工签核，运行 `validate_profiles.py --automatic-draft` 检查全范围档案和来源元数据；可选人工核验版另用 `--release`。",
              "本报告只记录当前数量，不替代逐条来源复核。", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()

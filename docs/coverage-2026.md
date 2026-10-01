# 2026 年资料覆盖率

自动生成报告。933 是纳入范围数量，不是调查完成数或档案数。

- 范围学校：933
- 已建单校档案：933
- 尚未建档：0
- 已人工签核档案：0
- 主色和建校年均已人工确认的档案：0

## 调查状态

| 状态 | 学校数 |
| --- | ---: |
| unresearched | 0 |
| in_progress | 0 |
| needs_review | 933 |
| reviewed | 0 |

## 关键字段

| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |
| --- | ---: | ---: | ---: | ---: | ---: |
| identity.name_en | 646 | 285 | 0 | 0 | 2 |
| identity.official_website | 139 | 794 | 0 | 0 | 0 |
| visual.color_primary | 545 | 379 | 0 | 6 | 3 |
| visual.color_secondary | 918 | 15 | 0 | 0 | 0 |
| visual.vi_url | 566 | 367 | 0 | 0 | 0 |
| visual.badge_description | 631 | 302 | 0 | 0 | 0 |
| culture.founded_year | 421 | 505 | 0 | 0 | 7 |
| culture.motto | 266 | 647 | 0 | 0 | 20 |
| culture.flower | 928 | 5 | 0 | 0 | 0 |
| culture.mascot | 928 | 5 | 0 | 0 | 0 |
| culture.anthem | 808 | 125 | 0 | 0 | 0 |
| resources.official_templates_url | 923 | 10 | 0 | 0 | 0 |
| resources.official_template_publisher | 923 | 10 | 0 | 0 | 0 |
| resources.official_template_terms | 926 | 5 | 0 | 2 | 0 |

## 首批双一流档案

剔除三所军校后共 144 所；已开始建档 144 所。建档不表示单校资料齐全。

| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |
| --- | ---: | ---: | ---: | ---: | ---: |
| identity.name_en | 18 | 125 | 0 | 0 | 1 |
| identity.official_website | 1 | 143 | 0 | 0 | 0 |
| visual.color_primary | 77 | 62 | 0 | 3 | 2 |
| visual.color_secondary | 134 | 10 | 0 | 0 | 0 |
| visual.vi_url | 67 | 77 | 0 | 0 | 0 |
| visual.badge_description | 79 | 65 | 0 | 0 | 0 |
| culture.founded_year | 35 | 107 | 0 | 0 | 2 |
| culture.motto | 10 | 127 | 0 | 0 | 7 |
| culture.flower | 142 | 2 | 0 | 0 | 0 |
| culture.mascot | 142 | 2 | 0 | 0 | 0 |
| culture.anthem | 113 | 31 | 0 | 0 | 0 |
| resources.official_templates_url | 136 | 8 | 0 | 0 | 0 |
| resources.official_template_publisher | 136 | 8 | 0 | 0 | 0 |
| resources.official_template_terms | 139 | 3 | 0 | 2 | 0 |

## 校史与校园地标

条目是有来源的校史节点节选及地标名称，不表示完整校史或完整校园清单。

| 字段 | 有资料学校 | 条目数 | 人工确认条目 |
| --- | ---: | ---: | ---: |
| culture.history_events | 319 | 597 | 0 |
| visual.landmarks | 4 | 9 | 0 |

## 主色取值方法

关键字段中的主色已找到数量包含两类资料：学校公布的数字标准色，以及本库标注用途的PPT建议色。建议色不等于官方VI标准色。

| 方法 | 学校数 | 含义 |
| --- | ---: | --- |
| official_vi | 32 | 学校发布的RGB/HEX标准值 |
| badge_sample | 1 | 校徽像素取样，PPT建议色 |
| manual_derived | 346 | 官网标识取色或人工推导，PPT建议色 |

## 官网页面发现

从候选网址访问公开首页；标题包含教育部校名且域名通过筛选才记为 `title_matched`。此步骤是自动判断。

- 已处理学校：933
- 无候选网址：1
- 首页标题匹配：780
- 标题匹配但站点归属待核对：1
- 找到概况页候选：705
- 访问或识别未完成：153
- 官网短证据候选：851（含需要排除的误匹配，不等于已录事实）

## 自动检索候选（仅供复核）

Wikidata 匹配及网站、建校年均是候选线索，未写入学校事实字段。

| 匹配状态 | 学校数 |
| --- | ---: |
| exact_ambiguous | 6 |
| exact_unique_classed | 582 |
| exact_unique_label_only | 319 |
| no_exact_match | 26 |

未取得唯一准确匹配的 32 所又尝试 API 搜索；搜索结果仍需辨认学校身份。
取得搜索候选 31 所；无结果 1 所；接口请求失败 0 所。

## 发布判断

正式公开版本要求 933 所逐校完成调查与人工复核，并通过 `validate_profiles.py --release`。
本报告只记录当前数量，不替代逐条来源复核。

# 2026 年资料覆盖率

自动生成报告。1412 是纳入范围数量，不是调查完成数或档案数。

- 范围学校：1412
- 已建单校档案：1412
- 尚未建档：0
- 已有附来源主色与建校年的档案：1383（含自动采集与建议色，不表示所有字段完备）
- 已人工签核档案：0
- 主色和建校年均已人工确认的档案：0

## 调查状态

| 状态 | 学校数 |
| --- | ---: |
| unresearched | 0 |
| in_progress | 0 |
| auto_collected | 1412 |
| needs_review | 0 |
| reviewed | 0 |

## 关键字段

| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |
| --- | ---: | ---: | ---: | ---: | ---: |
| identity.name_en | 1 | 1411 | 0 | 0 | 0 |
| identity.official_website | 203 | 1209 | 0 | 0 | 0 |
| visual.color_primary | 29 | 1383 | 0 | 0 | 0 |
| visual.color_secondary | 1379 | 32 | 0 | 0 | 1 |
| visual.vi_url | 781 | 631 | 0 | 0 | 0 |
| visual.badge_description | 1110 | 302 | 0 | 0 | 0 |
| culture.founded_year | 0 | 1412 | 0 | 0 | 0 |
| culture.motto | 524 | 878 | 0 | 0 | 10 |
| culture.flower | 1407 | 5 | 0 | 0 | 0 |
| culture.mascot | 1407 | 5 | 0 | 0 | 0 |
| culture.anthem | 1261 | 151 | 0 | 0 | 0 |
| resources.official_templates_url | 1388 | 24 | 0 | 0 | 0 |
| resources.official_template_publisher | 1388 | 24 | 0 | 0 | 0 |
| resources.official_template_terms | 1405 | 5 | 0 | 2 | 0 |

## 首批双一流档案

剔除三所军校后共 144 所；已开始建档 144 所。建档不表示单校资料齐全。

| 字段 | 未调查 | 已找到（自动） | 已找到（人工） | 未找到 | 冲突 |
| --- | ---: | ---: | ---: | ---: | ---: |
| identity.name_en | 0 | 144 | 0 | 0 | 0 |
| identity.official_website | 0 | 144 | 0 | 0 | 0 |
| visual.color_primary | 0 | 144 | 0 | 0 | 0 |
| visual.color_secondary | 127 | 16 | 0 | 0 | 1 |
| visual.vi_url | 41 | 103 | 0 | 0 | 0 |
| visual.badge_description | 79 | 65 | 0 | 0 | 0 |
| culture.founded_year | 0 | 144 | 0 | 0 | 0 |
| culture.motto | 9 | 134 | 0 | 0 | 1 |
| culture.flower | 142 | 2 | 0 | 0 | 0 |
| culture.mascot | 142 | 2 | 0 | 0 | 0 |
| culture.anthem | 112 | 32 | 0 | 0 | 0 |
| resources.official_templates_url | 135 | 9 | 0 | 0 | 0 |
| resources.official_template_publisher | 135 | 9 | 0 | 0 | 0 |
| resources.official_template_terms | 139 | 3 | 0 | 2 | 0 |

## 校史与校园地标

条目是有来源的校史节点节选及地标名称，不表示完整校史或完整校园清单。

| 字段 | 有资料学校 | 条目数 | 人工确认条目 |
| --- | ---: | ---: | ---: |
| culture.history_events | 320 | 600 | 0 |
| visual.landmarks | 4 | 9 | 0 |

## 主色取值方法

关键字段中的主色已找到数量包含两类资料：学校公布的数字标准色，以及本库标注用途的PPT建议色。建议色不等于官方VI标准色。

| 方法 | 学校数 | 含义 |
| --- | ---: | --- |
| official_vi | 73 | 学校发布的RGB/HEX标准值 |
| badge_sample | 721 | 校徽像素取样，PPT建议色 |
| manual_derived | 589 | 官网标识取色或人工推导，PPT建议色 |

## 社区资料

- 已匹配社区资源学校：306
- 资源入口条目：529
- 其中Beamer主题：29；Marp主题：2；校徽参考：295；校史参考：137
- 社区数据补充的事实：441（已计入关键字段，非校方现行声明）

资源索引见indexes/community-resources.csv。社区配色不计入学校主题色统计。

## PPT主字段验收

当前为v4主字段结构；招生、就业、排名、人数、面积和联系方式等扩展数据已剔除。
全校必备完成状态以[主字段覆盖](ppt-core-coverage-2026.md)和[data/review/ppt-core-coverage-2026.json](../data/review/ppt-core-coverage-2026.json)为准。
模板、VI、辅色与其他文化素材为可选材料，不以每校存在为前提。

## 附来源网址候选

- 已有附来源入口线索的学校：1412
候选不等于已确认官网。未确认时可在单校research.website_candidates中查看。

## 官网页面发现

从候选网址访问公开首页；标题包含教育部校名且域名通过筛选才记为 `title_matched`。此步骤是自动判断。

- 已处理学校：1412
- 无候选网址：0
- 首页标题匹配：1148
- 标题匹配但站点归属待核对：0
- 找到概况页候选：978
- 访问或识别未完成：264
- 官网短证据候选：851（含需要排除的误匹配，不等于已录事实）

## 自动检索候选（仅供复核）

Wikidata 匹配及网站、建校年均是候选线索，未写入学校事实字段。

| 匹配状态 | 学校数 |
| --- | ---: |
| exact_ambiguous | 6 |
| exact_unique_classed | 612 |
| exact_unique_label_only | 763 |
| no_exact_match | 31 |

历史补查表对当时未取得唯一准确匹配的学校尝试API搜索；不代表本轮全量本科缺口。
取得搜索候选 31 所；无结果 1 所；接口请求失败 0 所。

## 发布判断

本轮采用自动采集版：不要求人工签核，运行 `validate_profiles.py --automatic-draft` 检查全范围档案和来源元数据；可选人工核验版另用 `--release`。
本报告只记录当前数量，不替代逐条来源复核。

# 数据字段与状态

`data/universities-scope-2026.csv` 是 1,412 所本科身份与分类规则的唯一来源；所有本科院校在 `universities/<省级地区>/<标识码>/profile.yaml` 保存逐校事实。`indexes/`、`OFFICIAL.md` 和有社区资源时生成的 `COMMUNITY.md` 是派生视图。

## 身份与分类

`identity` 中的 `school_code`、`name_zh`、`province`、`city`（教育部“所在地”）、`level`、`authority`、`note`、`registry_source` 必须与范围表一致。`classification.scope_category` 是排他的纳入类别；`scope_tags` 可以重叠，机器名定义见下表。

| 标签 | 含义 |
| --- | --- |
| `double_first` | 命中第二轮双一流名单且在 2026 教育部普通高校名单内 |
| `name_ends_university` | 校名以“大学”结尾 |
| `short_name` | 校名不超过 5 个汉字 |
| `moe_note_blank` | 教育部原表备注栏为空 |
| `cooperative` | 备注含“合作” |
| `hainan_education_institution` | 备注含“海南自由贸易港” |
| `all_undergraduate` | 教育部原表本科层次，全量纳入 |
| `vocational_undergraduate` | 校名以职业大学或职业技术大学结尾 |
| `private` | 教育部备注含民办 |

标签是筛选线索，不自动推出公办性质、学校排名或资源使用许可。

## 可核查字段

`identity.name_en`、`identity.official_website`、`visual` 中的颜色、VI 页和校徽简述、`culture` 中的年份、校训、校花等、`resources` 中的官方入口与规则，统一使用：

```yaml
value: null
source: null
verified: unverified
checked_at: null
availability: unresearched
search_sources: []
```

`availability` 可为 `unresearched`、`found`、`not_found`、`conflict`。`found` 必须给出 `value`、网页 `source`、`checked_at`；`not_found` 必须给出检索过的 `search_sources` 与日期；`conflict` 保留至少两个带来源的 `candidates`，不得私自选一个值。`verified` 为 `unverified`、`auto` 或 `human`。AI 搜集的结果只能记作 `auto`，人工在网页核对后才能记作 `human`。

颜色值是六位 HEX，另需 `method`：`official_vi`、`badge_sample`、`manual_derived`。后两种是建议色，不可说成学校官方标准色。建校年为整数，另需 `basis` 指出采用的历史起点。`history_events` 至多 5 条，`landmarks` 至多 3 条，每条都单独附来源、日期和核实状态。所有简述应简短改写，避免复制整段学校介绍。

`research.status` 为 `unresearched`、`in_progress`、`auto_collected`、`needs_review`、`reviewed`。`reviewed` 必须有 `checked_at` 与 `reviewed_by`。单校状态不能代替逐字段核实状态。

## 记录示例

清华大学官方章程记载清华学堂始建于 1911 年，示例档案将 1911 写入 `founded_year.value`，将“清华学堂始建年份”写入 `basis`，并保存章程 URL。北京大学官方 VI 常见问题页的 RGB 与紧邻的十六进制色值不一致，示例档案将两值置于 `candidates`，状态为 `conflict`。

## 社区来源与资源

GitHub 数据填充的事实增加 `source_type: community_dataset`、`upstream_repository`、`upstream_commit`、`upstream_record_name`、`upstream_license`、`source_as_of` 与用途说明。社区英文名保留上游时间，不认定其现行官方效力。原值与社区候选不同，进入 `public-repository-differences-2026.csv`；不直接覆盖原值。

可选 `resources.community_resources` 是列表。每条包含 `title`、`url`、`source`、`publisher`、`kind`、`official: false`、`license`、40位 `commit`、`verified: auto`、`checked_at`、`usage_note`。无许可时 `license: null`，仅链接。`kind` 为 `beamer_theme`、`marp_theme`、`logo_reference` 等具体资源类型。

可选 `palette` 记录社区主题色，含 HEX `value`、`method: community_theme`、提取 `basis`，以及可选 `source`。这类值只在社区资源内，不参与官方主题色覆盖率。Beamer 与 Marp 不等于 PowerPoint 的 PPTX 文件。

`research.status: auto_collected` 表示已采集到部分资料，须有采集日期；不代表逐字段完备。本轮无需 `reviewed_by` 或 `verified: human`。原来的 `needs_review` 状态兼容保留，人工审定规则仍供未来选用。

`research.website_candidates`可保存尚未确认官网时的附来源入口，状态为`unverified_candidate`，不会自动变成`identity.official_website`。`website_candidates_updated_at`记录线索同步日期。

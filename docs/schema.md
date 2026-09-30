# 数据字段与状态

`data/universities-scope-2026.csv` 是 933 所范围身份与筛选规则的唯一来源；已开始调查的学校在 `universities/<省级地区>/<标识码>/profile.yaml` 保存逐校事实。`indexes/` 与 `OFFICIAL.md` 是派生视图。总索引的 `profile_path` 为空表示尚未建档。

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
| `user_selected` | 用户指定纳入 |

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

`research.status` 为 `unresearched`、`in_progress`、`needs_review`、`reviewed`。`reviewed` 必须有 `checked_at` 与 `reviewed_by`。单校状态不能代替逐字段核实状态。

## 记录示例

清华大学官方章程记载清华学堂始建于 1911 年，示例档案将 1911 写入 `founded_year.value`，将“清华学堂始建年份”写入 `basis`，并保存章程 URL。北京大学官方 VI 常见问题页的 RGB 与紧邻的十六进制色值不一致，示例档案将两值置于 `candidates`，状态为 `conflict`。

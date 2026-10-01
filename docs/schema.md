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

## v3字段并集

当前`schema_version: 3`。新增字段全部列于[data/profile-schema-v3.yaml](../data/profile-schema-v3.yaml)；旧v2档案可由`expand_repository_fields.py`无损增加空字段，已有事实和人工选择保留。当前全量交付要求1412份v3档案；校验器仍能读取v2历史档案。

新增事实保留既有`value/source/verified/checked_at/availability/search_sources`封装；`value`按字段定义为短文本、文本列表、数字或坐标对象。不能把未知数值写成0或空字符串。

| 分组 | 新增内容 |
| --- | --- |
| identity | 中英文简称、别名、检索slug、带命名空间的外部标识 |
| institution | 类型、性质、国家、授课语言、院校群与历史项目标签 |
| location | 地址、邮编、校区、坐标（latitude/longitude/crs/precision/location_kind） |
| overview | 中英文短简介；社区评论保留在快照，不转成客观事实 |
| statistics | 学生、教职工人数、校园面积；必须有统计日期source_as_of与basis |
| academics | 双一流学科、学位授权、按subject/round/grade保存的评估节选 |
| rankings | publisher/ranking_name/year/scope/rank/score/indicators/upstream_url |
| admissions | cutoffs、major_cutoffs、plans，按地区、年份、科类、批次及招生类型区分 |
| employment | 概况、报告入口、按毕业届次与统计口径保存的outcomes |
| resources/contacts | 招生、就业、英文、信息公开入口与公开办公电话/邮箱 |
| visual | logo_assets、color_palette、vi_resources |
| community | snapshots，引用本库保留许可的上游匹配记录子集 |

`admissions.cutoffs`含`minimum_score/minimum_rank/score_difference/enrolled_count/major_group/reference_only`；`major_cutoffs`另含`major_name/major_code/major_group/subject_requirements`；`plans`含`major_name/major_code/planned_count/tuition/duration_years/subject_requirements`。三者共同包含`year/region/curriculum/batch/enrollment_type`及来源元数据。缺项不能从学校最低分或上游未注明的专业组推断。`location.campuses`逐条包含`name/address/coordinates`及来源；`employment.outcomes`包含`graduation_year/metric/value/unit/basis`及来源。

### 逐文件视觉资源

`visual.logo_assets`包含`asset_id/kind/title/url/source/file_name/upstream_path/publisher/official/repository/commit/repository_license/asset_license/rights_holder/format/width/height/vector/representation/has_alpha/transparent_background/sha256/byte_size/access_status/availability/verified/checked_at/usage_note`。`kind`区分`badge/wordmark/combination/anniversary/site_identity`；学校全称或唯一英文全名匹配后才归档。`site_identity`是学校官网页眉标识，具体校徽/校名构成待核验，不能自动称作纯校徽。此类`official: true`仅表示校方页面发布，另存`identity_basis`与`source_type: official_website`，不表示通过了VI版本或授权核验。`variant/dimensions_in_filename`只是文件名提示，不代替实测尺寸或HEX。

`access_status`为`indexed_not_fetched/content_inspected/inspection_failed`。实测格式来自文件内容，不相信扩展名；`representation`区分纯矢量、SVG内嵌位图和普通位图。`vector: false`的SVG可以是内嵌位图。SVG透明背景无法仅凭填充属性确认时保持null；viewBox不等于像素尺寸；mm等尺寸保留在intrinsic_width/intrinsic_height而不假称像素。只在读取成功后记sha256/byte_size。检查失败保留实际尝试的网址及原因，可继续从其他来源取得同校文件。

`visual.color_palette`逐条含HEX`value`、`rgb`、`cmyk/pantone`、`role`、`method`、`official`、`source`、`verified/checked_at/availability/basis`和可选上游版本/asset_id。方法增加`community_theme/community_logo_sample`；只有`official_vi`允许`official: true`。取样值属于建议，不覆盖已有官方主色或冲突结论。RGB由HEX精确转换；CMYK/Pantone必须另有标准来源，不做无依据换算。

可选`label`保留原色名；`current: false`标出已转为历史参考的记录。官网新VI手册替代旧标识或图片建议色时，保存替换台账并保留原依据。RGB/HEX不一致时，主色或辅色字段均可使用`conflict/candidates`；全部候选另生成`indexes/color-conflicts.csv`，不直接选值。手册中“并列标准色”“主色系”和“特殊用途红色”等用途保存在`basis`，不自动改称唯一辅助色。

`visual.vi_resources`记录学校资源链接、提供的资源种类、格式、校园认证要求和社区依据；社区目录指向官方页面不等于资源由该社区官方发布。

### 上游快照与差异

MIT上游匹配数据存于`data/external/<仓库>/matched-fields.jsonl`，保留原始字段、学校标识码、来源及独立LICENSE。`community.snapshots`保存`repository/commit/data_path/school_code/upstream_record_name/upstream_fields/source/license/data_as_of/verified/checked_at`；原字段有主观评价、旧数据、占位文字或错误链接时仍可从快照追溯，但不自动成为本库采纳的学校事实。没有兼容数据许可的仓库只提取资源链接事实，不再分发完整原数据。

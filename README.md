# 高校 PPT 资料库

为个人和 AI 助手制作高校主题 PPT 整理可检索的学校事实、视觉线索和资源入口。

**当前范围：教育部 2026 年名单中的全部 1,412 所本科院校，均已建档。** 含普通本科、职业本科、民办与合作办学院校；不再采用旧版 933 所选校过滤。资料持续自动补采，本轮不要求人工签核。建档数量与字段覆盖率分别统计，见[覆盖率报告](docs/coverage-2026.md)。

## 找学校与资料

1. 在[总索引](indexes/catalog.csv)按校名、学校标识码、地区查找，也可浏览[地区](indexes/by-province.csv)、[类别](indexes/by-category.csv)、[标签](indexes/by-tag.csv)、[状态](indexes/by-status.csv)。
2. 打开索引中的 `profile_path`，读取唯一事实源 `profile.yaml`。`PROFILE.md` 是逐校便读档案，`VISUAL.md` 汇总逐文件校徽、校名与配色，`OFFICIAL.md` 展示官方 PPT 入口；有社区资源的学校另有 `COMMUNITY.md`。
3. 每字段先看 `availability`、`source`、`verified`、`checked_at`。自动采集标记为 `auto`，可按来源和用途使用；冲突、未调查和检索后未找到均显式保留。

示例：[清华大学](universities/北京市/4111010003/profile.yaml)、[北京大学](universities/北京市/4111010001/profile.yaml)、[西湖大学](universities/浙江省/4133014626/profile.yaml)。PPT 和 AI 助手的完整使用方法见[数据指南](docs/data-guide.md)。

制作PPT优先读取[精简JSONL](indexes/ppt-profiles.jsonl)或[配套CSV](indexes/ppt-profiles.csv)，包含全部1412所身份、标识推荐依据、分层配色、模板及短简介；字段与查询命令见[PPT导出v1说明](docs/ppt-export-v1.md)。也可从[单校素材索引](indexes/ppt-starter.csv)开始，接着查[模板与素材入口](indexes/ppt-resources.csv)。学校通用、院系专用、社区PPTX/Marp/Beamer和TikZ标识源码分别标注；读取方法见[PPT使用指南](docs/ppt-guide.md)。

[下一阶段计划](docs/next-phase-plan-2026.md)明确统一校验、PPT精简数据、素材检索预览、针对性补采、版本交付和来源变更维护的顺序与验收标准。

## GitHub字段并集与视觉资料

v3在原有学校身份、文化与官方资源字段上新增27个事实字段、12个结构化集合，纳入中英文简称、类型与性质、授课语言、地址/坐标、学科、人数/面积、历史排名、招生/就业数据的完整口径，并保留可追溯社区快照。实际填充数量和上游字段逐项落点见[字段比较与覆盖报告](docs/github-field-union-2026.md)，有字段不表示已取得对应数据。

- [校徽文件索引](indexes/logo-assets.csv)：具体文件URL、实际格式、宽高、矢量/透明信息、文件哈希、访问状态和权利说明。
- [调色板索引](indexes/color-palettes.csv)：HEX、RGB、用途与取值方法；官方标准、社区主题、取色建议分别标明。没有依据的CMYK/Pantone保持空值。
- [色值冲突索引](indexes/color-conflicts.csv)：主色与辅色/并列色的各来源候选、差异原因，保留RGB和HEX不一致等问题。
- [扩展目录](indexes/enriched-catalog.csv)、[新增事实](indexes/extended-facts.csv)、[排名历史](indexes/rankings.csv)、[学科评估](indexes/subject-assessments.csv)、[录取参考](indexes/admission-cutoffs.csv)。
- [校区索引](indexes/campuses.csv)与[官网简介及开源补采报告](docs/overview-enrichment-progress-2026.md)：短摘要、人数、面积与授权点；看统计日期、近似标注及总数/子群口径。
- [AI用JSONL全集](indexes/profiles.jsonl)：从1412份档案生成，每行一校；可用`school_code`稳定关联各索引。
- [官方视觉规范补采进度](docs/visual-completion-progress-2026.md)：新增标准色色卡、仅印刷色规范、数字冲突及补确认的官网入口。
- [实际模板文件](indexes/ppt-template-files.csv)：已读取PPTX的页数、画幅、声明字体、可编辑文本节点与哈希；压缩包内模板逐文件列出。
- [校徽、配色与PPT缺口补采](docs/visual-gap-progress-2026.md)：官网页头/CSS、当前校名社区目录、组合版式和实际文件读取的增量与剩余缺口。

校徽图形只保存逐文件链接和内容元数据。社区仓库的代码/数据许可与学校标识的图形授权分别记录；文件可访问、格式已检查、图形为学校现行版本是不同状态。记录中的历史排名和招生参考值不自动成为现行官方结论。

`download_kind=archive_member` 表示校徽位于上游压缩包，需按 `archive_url` 和 `archive_member` 读取，主URL不是PNG直链。统计 `source_as_of=undated` 表示原文未注明统计日期；`checked_at` 是采集日期。约数保留 `approximate` 与 `original_notation`，使用人数或面积时读取 `basis`。

## 分类和层级

```text
universities-index.csv                  教育部普通高校原表：2952 所，含专科
data/universities-scope-2026.csv        本科范围：1412 所，唯一范围表
data/source-manifest.yaml              官方附件、哈希、范围与采集政策
data/external/                         已匹配的许可数据子集、上游版本和许可
data/review/                           检索台账、候选、来源差异与补采队列
universities/<省级地区>/<学校标识码>/
   profile.yaml                        单校唯一事实源
   PROFILE.md                          全字段便读档案
   VISUAL.md                           逐文件视觉资源与配色
   OFFICIAL.md                         官方资源生成视图
   COMMUNITY.md                        有社区资源时生成的便读视图
indexes/                              从范围表与档案派生的检索索引
docs/                                 需求、字段、覆盖率、采集说明
scripts/                              采集、导入、生成与校验脚本
```

省级分组和学校身份取自教育部原表，标识码作为稳定身份键。主类别互斥，标签可重叠：双一流、职业本科、合作办学、民办等可交叉查询。空备注不推断为公办。旧选校输入保留在 `data/selection-source/`，仅作历史记录。

## 本地生成与校验

需 Python 3.9+。统一质量检查安装 `requirements-quality.txt`，包含生成、图像解析测试和JSON Schema校验依赖。CI验证Python 3.9与3.13；检查已有数据时不联网采集。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/render_enriched.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/ingest/build_ppt_indexes.py
.venv/bin/python scripts/ingest/build_ppt_profiles.py
.venv/bin/python scripts/validate/report_field_union.py
.venv/bin/python scripts/validate/report_official_extensions.py
.venv/bin/python scripts/validate/report_overview_progress.py
.venv/bin/python scripts/validate/report_visual_completion.py
.venv/bin/python scripts/validate/report_visual_gaps.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/report_research.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/check.py
```

统一检查执行档案语义、两套JSON Schema、单元测试、六项生成一致性及仓库只读检查。失败会显示学校标识码/字段或过期文件位置。提交、PR和手动触发均运行[GitHub Actions](https://github.com/yangxiake/university-design-db/actions/workflows/quality.yml)，实现与验收说明见[质量检查文档](docs/quality-checks.md)。

联网补采流程：

```bash
.venv/bin/python scripts/ingest/build_2026.py
.venv/bin/python scripts/ingest/seed_profiles.py --all
.venv/bin/python scripts/ingest/collect_wikidata_candidates.py
.venv/bin/python scripts/ingest/import_public_repositories.py
.venv/bin/python scripts/ingest/expand_repository_fields.py
.venv/bin/python scripts/ingest/import_additional_public_data.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/ingest/discover_official_pages.py --priority 2 --resume
.venv/bin/python scripts/ingest/import_confirmed_homepages.py
.venv/bin/python scripts/ingest/collect_homepage_identity.py
.venv/bin/python scripts/ingest/research_all_schools.py --resume
.venv/bin/python scripts/ingest/apply_context_corrections.py
.venv/bin/python scripts/ingest/import_research_claims.py
.venv/bin/python scripts/ingest/import_scope_extensions.py
.venv/bin/python scripts/ingest/collect_official_extensions.py --resume
.venv/bin/python scripts/ingest/import_visual_refresh.py
.venv/bin/python scripts/ingest/import_visual_refresh.py --decisions data/review/visual-guides-decisions-2026.yaml
.venv/bin/python scripts/ingest/collect_visual_attachments.py
.venv/bin/python scripts/ingest/collect_visual_directory.py --resume
.venv/bin/python scripts/ingest/collect_visual_directory.py --import-only --recover-confirmed-host
.venv/bin/python scripts/ingest/collect_ppt_resources.py
.venv/bin/python scripts/ingest/import_cnlogo_metadata.py
.venv/bin/python scripts/ingest/import_community_ppt_metadata.py
.venv/bin/python scripts/ingest/import_logo_layouts.py
.venv/bin/python scripts/ingest/collect_header_css_marks.py
.venv/bin/python scripts/ingest/collect_community_logo_gaps.py
.venv/bin/python scripts/ingest/import_visual_refresh.py --decisions data/review/visual-gap-color-decisions-2026.yaml
.venv/bin/python scripts/ingest/inspect_template_files.py
.venv/bin/python scripts/ingest/collect_official_overviews.py --resume
.venv/bin/python scripts/ingest/import_overview_supplements.py
.venv/bin/python scripts/ingest/sync_source_candidates.py
```

范围构建校验官方附件哈希，也支持本地附件。社区导入按[仓库清单](data/external/repositories.yaml)锁定上游提交；只读数据，不执行上游代码。采集结果会随网站变化，详见[采集说明](docs/source-collection.md)。采集完成后重新执行生成与校验命令。可选的 `validate_profiles.py --release` 专供未来人工审定版本使用，本轮验收使用 `--automatic-draft`。

视觉文件检查需要`requirements-research.txt`中的Pillow。只重试解析/访问失败的视觉文件可运行`.venv/bin/python scripts/ingest/expand_repository_fields.py --retry-visual-errors`，再重新生成视图、索引和覆盖报告。

`collect_official_extensions.py`补采已确认官网的地址、邮编、公开办公/招生联系方式、门户入口和页眉标识链接；原始网页/图片不入库。`--resume`继续未完成学校，`--retry-gaps`重试首页访问失败的学校，`--import-only`从已有台账重建导入。官网标识取色只进入参考调色板，保留已有官方主色结论。

失败的官网标识文件可用`collect_official_extensions.py --retry-asset-errors`单独重试原链接及同路径另一协议；尺寸不符合标识要求的图片进入排除记录。联系与门户进度见[官网扩展报告](docs/official-extension-progress-2026.md)。

`collect_official_overviews.py --retry-missing`从已有台账缺项出发尝试不同简介入口和官网导航；`--collect-only`先保存证据台账，`--reparse-cache --import-only`用忽略目录中的HTML重新解析并导入，原文不发布。最后运行`import_overview_supplements.py`按固定证据规则核对统计卡片；页面内容变化导致证据不匹配时停止该导入。

`inspect_template_files.py --retry-errors`重试未读取的模板文件；资源重新导入后运行`--import-only`恢复已有结构元数据，再生成PPT索引。读取有文件/展开大小及时间上限；公开文件仅存于忽略目录，仓库只发布URL、结构统计和哈希。

`collect_header_css_marks.py`补查已确认官网的静态页头标识与CSS文件引用，支持`--collect-only`和`--import-only`。`collect_community_logo_gaps.py --retry-errors`只重试网络失败及尚未读到预览文件的社区目录；更名暂停、名称不匹配和不存在的页面不自动采纳。社区网页没有Git提交，以页面与图像哈希、学校标识码和现行完整校名追溯。

## 来源与许可

学校官网、教育部门及校方提交的招生资料优先。公开 GitHub 数据按完整校名匹配到教育部标识码，记录来源类型、上游版本和日期。社区英文名不自动等同现行官方译名；社区配色仅写入资源参考，官方 VI 标准色、标识取样建议色分别标记方法。访问失败会尝试不同域名或页面入口，仍失败时保留记录，不能将其写成“学校没有”。

原创脚本按 [MIT](LICENSE)，原创数据整理按 [CC BY 4.0](LICENSE-DATA.md)。[第三方数据说明](data/external/README.md)列出独立许可；本库许可不替学校或社区作者授权校徽、字体、照片与模板。贡献方法见[贡献指南](CONTRIBUTING.md)。

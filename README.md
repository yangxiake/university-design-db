# 高校 PPT 资料库

为个人和 AI 助手制作高校主题 PPT 整理可检索的学校事实、视觉线索和资源入口。

**在线使用：[高校 PPT 素材目录](https://yangxiake.github.io/university-design-db/)。** 搜索学校，查看标识、配色和模板入口，复制单校资料给 AI；无需安装本地环境。

仓库已[公开发布到 GitHub](https://github.com/yangxiake/university-design-db)，无需登录即可查看代码、数据和下载 Release 资料包。也可下载后通过本地 HTTP 服务打开素材目录。main 更新后由 GitHub Actions 自动检查、构建并部署在线站点；部署方法见[GitHub Pages 说明](docs/github-pages.md)。

最新资料包：[v0.4.5-20261004](https://github.com/yangxiake/university-design-db/releases/tag/v0.4.5-20261004)，统一按钮、控件状态和展开动画，调整卡片对齐、间距及手机布局，见[界面协调性更新](docs/releases/2026-10-04-viewer-consistency.md)。保留上一版的[预览与资源合并改进](docs/releases/2026-10-03-viewer-preview.md)，网页搜索已移除内部分类标签。主字段资料沿用[v0.4.2补采批次](docs/releases/2026-10-03-other-sources.md)，这是附来源的自动整理预发布版，尚未全量补齐；仅收现行已确认资料，剩余32所、59项缺口逐校保留。

**当前范围：教育部 2026 年名单中的全部 1,412 所本科院校，均已建档。** 含普通本科、职业本科、民办与合作办学院校；不再采用旧版 933 所选校过滤。按用户要求，剩余缺口补采已暂停，当前优化素材目录界面与检索。建档数量与字段覆盖率分别统计，见[覆盖率报告](docs/coverage-2026.md)。

## 找学校与资料

直接打开[在线素材目录](https://yangxiake.github.io/university-design-db/)：检索1412所学校，比较标识、查看配色证据和模板条件，并复制单校资料给AI。离线使用时，下载仓库后在根目录运行`python3 -m http.server 8765 --bind 127.0.0.1`，打开`http://127.0.0.1:8765/viewer/`；完整用法见[素材目录说明](docs/viewer-guide.md)。

1. 在[总索引](indexes/catalog.csv)按校名、学校标识码、地区查找，也可浏览[地区](indexes/by-province.csv)、[类别](indexes/by-category.csv)、[标签](indexes/by-tag.csv)、[状态](indexes/by-status.csv)。
2. 打开索引中的 `profile_path`，读取唯一事实源 `profile.yaml`。`PROFILE.md` 是逐校便读档案，`VISUAL.md` 汇总逐文件校徽、校名与配色，`OFFICIAL.md` 展示官方 PPT 入口；有社区资源的学校另有 `COMMUNITY.md`。
3. 每字段先看 `availability`、`source`、`verified`、`checked_at`。自动采集标记为 `auto`，可按来源和用途使用；冲突、未调查和检索后未找到均显式保留。

示例：[清华大学](universities/北京市/4111010003/profile.yaml)、[北京大学](universities/北京市/4111010001/profile.yaml)、[西湖大学](universities/浙江省/4133014626/profile.yaml)。PPT 和 AI 助手的完整使用方法见[数据指南](docs/data-guide.md)。

制作PPT优先读取[精简JSONL](indexes/ppt-profiles.jsonl)或[配套CSV](indexes/ppt-profiles.csv)，包含全部1412所身份、标识推荐依据、分层配色、模板及短简介；字段与查询命令见[PPT导出v1说明](docs/ppt-export-v1.md)。也可从[单校素材索引](indexes/ppt-starter.csv)开始，接着查[模板与素材入口](indexes/ppt-resources.csv)。学校通用、院系专用、社区PPTX/Marp/Beamer和TikZ标识源码分别标注；读取方法见[PPT使用指南](docs/ppt-guide.md)。

[下一阶段计划](docs/next-phase-plan-2026.md)明确统一校验、PPT精简数据、素材检索预览、针对性补采、版本交付和来源变更维护的顺序与验收标准。

**当前采集范围已收窄为PPT主字段。** 必备：学校身份与英文名、可读校徽/校名标识、附来源主题主色、建校年。校训、模板、VI、校史节点等为可选补充。招生、就业、排名、人数、面积、地址与联系方式等高维护成本数据已从现行档案和索引剔除，结构升级为v4。

逐校完成状态见[主字段覆盖报告](docs/ppt-core-coverage-2026.md)，补采只按[主字段队列](data/review/ppt-core-queue-2026.csv)推进；范围定义见[ppt-core-fields.yaml](data/ppt-core-fields.yaml)。最新图形、色值与文件证据见[M4第二批报告](docs/m4-batch02-progress-2026.md)。

## 开源来源与视觉资料

仅保留对PPT身份、配色和模板有帮助的上游字段，固定提交并保留许可。字段比较见[开源来源与核心映射](docs/github-field-union-2026.md)。未取得独立图形授权的资源保留原链接，代码许可不作为校徽授权。

- [校徽文件索引](indexes/logo-assets.csv)：具体文件URL、实际格式、宽高、矢量/透明信息、文件哈希、访问状态和权利说明。
- [调色板索引](indexes/color-palettes.csv)：HEX、RGB、用途与取值方法；官方标准、社区主题、取色建议分别标明。没有依据的CMYK/Pantone保持空值。
- [色值冲突索引](indexes/color-conflicts.csv)：主色与辅色/并列色的各来源候选、差异原因，保留RGB和HEX不一致等问题。
- [核心资料目录](indexes/enriched-catalog.csv)与[主字段事实索引](indexes/core-facts.csv)：按学校和字段查询附来源记录。
- [AI用JSONL全集](indexes/profiles.jsonl)：从1412份档案生成，每行一校；可用`school_code`稳定关联各索引。
- [官方视觉规范补采进度](docs/visual-completion-progress-2026.md)：新增标准色色卡、仅印刷色规范、数字冲突及补确认的官网入口。
- [实际模板文件](indexes/ppt-template-files.csv)：已读取PPTX的页数、画幅、声明字体、可编辑文本节点与哈希；压缩包内模板逐文件列出。
- [校徽、配色与PPT缺口补采](docs/visual-gap-progress-2026.md)：官网页头/CSS、当前校名社区目录、组合版式和实际文件读取的增量与剩余缺口。

校徽图形只保存逐文件链接和内容元数据。社区仓库的代码/数据许可与学校标识的图形授权分别记录；文件可访问、格式已检查、图形为学校现行版本是不同状态。

`download_kind=archive_member` 表示校徽位于上游压缩包，需按 `archive_url` 和 `archive_member` 读取，主URL不是PNG直链。`checked_at` 是读取日期；`source_revision`、上游提交与哈希用于追溯当时版本。

`download_kind=document_page` 表示标识位于原PDF的指定页和嵌入图区域，需要从原PDF提取。保留`document_page`、`document_image_sha256`与`document_mark_region`，不将PDF当作独立透明图片或矢量标识。

## 分类和层级

```text
universities-index.csv                  教育部普通高校原表：2952 所，含专科
data/universities-scope-2026.csv        本科范围：1412 所，唯一范围表
data/source-manifest.yaml              官方附件、哈希、范围与采集政策
data/external/                         已匹配的许可数据子集、上游版本和许可
data/review/                           检索台账、候选、来源差异与补采队列
universities/<省级地区>/<学校标识码>/
   profile.yaml                        单校唯一事实源
   PROFILE.md                          PPT主字段便读档案
   VISUAL.md                           逐文件视觉资源与配色
   OFFICIAL.md                         官方资源生成视图
   COMMUNITY.md                        有社区资源时生成的便读视图
indexes/                              从范围表与档案派生的检索索引
viewer/                               素材检索页面、匹配规则和测试
   data/catalog.json                  轻量检索目录，含来源和格式等筛选描述
   data/provinces/<地区>.json           按需载入的地区资料，保留完整PPT导出记录
docs/                                 需求、字段、覆盖率、采集说明
scripts/                              采集、导入、生成与校验脚本
```

省级分组和学校身份取自教育部原表，标识码作为稳定身份键。主类别互斥，标签可重叠：双一流、职业本科、合作办学、民办等可交叉查询。空备注不推断为公办。旧选校输入保留在 `data/selection-source/`，仅作历史记录。

## 本地生成与校验

需 Python 3.9+；统一质量检查还使用Node.js 24运行网页匹配规则测试，无npm依赖。安装 `requirements-quality.txt`，包含生成、图像解析测试和JSON Schema校验依赖。GitHub CI使用Python 3.9与3.13；检查已有数据时不联网采集。只浏览素材目录无需Node.js。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/render_enriched.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/ingest/build_ppt_indexes.py
.venv/bin/python scripts/ingest/build_ppt_profiles.py
.venv/bin/python scripts/ingest/build_viewer.py
.venv/bin/python scripts/validate/report_field_union.py
.venv/bin/python scripts/validate/report_visual_completion.py
.venv/bin/python scripts/validate/report_visual_gaps.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/report_ppt_core.py
.venv/bin/python scripts/validate/report_research.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/check.py
```

统一检查执行档案语义、两套JSON Schema、Python与网页规则测试、七项生成一致性及仓库只读检查。失败会显示学校标识码/字段或过期文件位置。提交、PR和手动触发均运行[GitHub Actions](https://github.com/yangxiake/university-design-db/actions/workflows/quality.yml)，实现与验收说明见[质量检查文档](docs/quality-checks.md)。

主字段补采流程（只采缺项）：

```bash
.venv/bin/python scripts/ingest/collect_ppt_core.py --resume --collect-only
.venv/bin/python scripts/ingest/collect_ppt_core.py --import-only
.venv/bin/python scripts/ingest/collect_wikidata_core.py --include-label-only --apply
.venv/bin/python scripts/ingest/collect_wikipedia_core.py --collect-only
.venv/bin/python scripts/ingest/collect_wikipedia_core.py --import-only
.venv/bin/python scripts/ingest/collect_chinaschool_core.py --collect-only
.venv/bin/python scripts/ingest/collect_chinaschool_core.py --import-only
.venv/bin/python scripts/ingest/collect_homepage_identity.py
.venv/bin/python scripts/ingest/collect_header_css_marks.py
.venv/bin/python scripts/ingest/fill_ppt_reference_colors.py
.venv/bin/python scripts/ingest/collect_ppt_site_colors.py --collect-only
.venv/bin/python scripts/ingest/collect_ppt_site_colors.py --import-only
.venv/bin/python scripts/validate/report_ppt_core.py
```

官网来源优先；社区来源与取样建议明确标记。只填尚未取得的字段，保留已有冲突和人工决定。标识、VI、模板按已有公开入口补查；不再运行旧版全字段扩展、统计和就业采集器。上游数据按[固定版本清单](data/external/repositories.yaml)读取；导入主字段子集后运行 `prune_ppt_data.py` 约束当前档案。采集完成后重建七项派生内容并执行统一检查。

`inspect_template_files.py --retry-errors`重试未读取的模板文件；资源重新导入后运行`--import-only`恢复已有结构元数据，再生成PPT索引。读取有文件/展开大小及时间上限；公开文件仅存于忽略目录，仓库只发布URL、结构统计和哈希。

`collect_header_css_marks.py`补查已确认官网的静态页头标识与CSS文件引用，支持`--collect-only`和`--import-only`。`collect_community_logo_gaps.py --retry-errors`只重试网络失败及尚未读到预览文件的社区目录；更名暂停、名称不匹配和不存在的页面不自动采纳。社区网页没有Git提交，以页面与图像哈希、学校标识码和现行完整校名追溯。

## 来源与许可

学校官网、教育部门及校方正式文件优先。公开 GitHub 数据按完整校名匹配到教育部标识码，记录来源类型、上游版本和日期。社区英文名不自动等同现行官方译名；社区配色仅写入资源参考，官方 VI 标准色、标识取样建议色分别标记方法。访问失败会尝试不同域名或页面入口，仍失败时保留记录，不能将其写成“学校没有”。

原创脚本按 [MIT](LICENSE)，原创数据整理按 [CC BY 4.0](LICENSE-DATA.md)。[第三方数据说明](data/external/README.md)列出独立许可；本库许可不替学校或社区作者授权校徽、字体、照片与模板。贡献方法见[贡献指南](CONTRIBUTING.md)。

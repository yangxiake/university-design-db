# 高校 PPT 资料库

为个人和 AI 助手制作高校主题 PPT 整理可检索的学校事实、视觉线索和资源入口。

**当前范围：教育部 2026 年名单中的全部 1,412 所本科院校，均已建档。** 含普通本科、职业本科、民办与合作办学院校；不再采用旧版 933 所选校过滤。资料持续自动补采，本轮不要求人工签核。建档数量与字段覆盖率分别统计，见[覆盖率报告](docs/coverage-2026.md)。

## 找学校与资料

1. 在[总索引](indexes/catalog.csv)按校名、学校标识码、地区查找，也可浏览[地区](indexes/by-province.csv)、[类别](indexes/by-category.csv)、[标签](indexes/by-tag.csv)、[状态](indexes/by-status.csv)。
2. 打开索引中的 `profile_path`，读取唯一事实源 `profile.yaml`。`PROFILE.md` 是逐校便读档案，`VISUAL.md` 汇总逐文件校徽、校名与配色，`OFFICIAL.md` 展示官方 PPT 入口；有社区资源的学校另有 `COMMUNITY.md`。
3. 每字段先看 `availability`、`source`、`verified`、`checked_at`。自动采集标记为 `auto`，可按来源和用途使用；冲突、未调查和检索后未找到均显式保留。

示例：[清华大学](universities/北京市/4111010003/profile.yaml)、[北京大学](universities/北京市/4111010001/profile.yaml)、[西湖大学](universities/浙江省/4133014626/profile.yaml)。PPT 和 AI 助手的完整使用方法见[数据指南](docs/data-guide.md)。

## GitHub字段并集与视觉资料

v3在原有学校身份、文化与官方资源字段上新增27个事实字段、12个结构化集合，纳入中英文简称、类型与性质、授课语言、地址/坐标、学科、人数/面积、历史排名、招生/就业数据的完整口径，并保留可追溯社区快照。实际填充数量和上游字段逐项落点见[字段比较与覆盖报告](docs/github-field-union-2026.md)，有字段不表示已取得对应数据。

- [校徽文件索引](indexes/logo-assets.csv)：具体文件URL、实际格式、宽高、矢量/透明信息、文件哈希、访问状态和权利说明。
- [调色板索引](indexes/color-palettes.csv)：HEX、RGB、用途与取值方法；官方标准、社区主题、取色建议分别标明。没有依据的CMYK/Pantone保持空值。
- [扩展目录](indexes/enriched-catalog.csv)、[新增事实](indexes/extended-facts.csv)、[排名历史](indexes/rankings.csv)、[学科评估](indexes/subject-assessments.csv)、[录取参考](indexes/admission-cutoffs.csv)。
- [AI用JSONL全集](indexes/profiles.jsonl)：从1412份档案生成，每行一校；可用`school_code`稳定关联各索引。

校徽图形只保存逐文件链接和内容元数据。社区仓库的代码/数据许可与学校标识的图形授权分别记录；文件可访问、格式已检查、图形为学校现行版本是不同状态。记录中的历史排名和招生参考值不自动成为现行官方结论。

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

需 Python 3.9+，联网研究另安装 `requirements-research.txt`。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/render_enriched.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/report_field_union.py
.venv/bin/python scripts/validate/report_research.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/validate/validate_profiles.py --automatic-draft
.venv/bin/python scripts/ingest/build_indexes.py --check
.venv/bin/python scripts/ingest/render_official.py --check
.venv/bin/python scripts/ingest/render_community.py --check
.venv/bin/python scripts/ingest/render_enriched.py --check
.venv/bin/python -m unittest discover -s scripts/validate -p 'test_*.py'
```

联网补采流程：

```bash
.venv/bin/python scripts/ingest/build_2026.py
.venv/bin/python scripts/ingest/seed_profiles.py --all
.venv/bin/python scripts/ingest/collect_wikidata_candidates.py
.venv/bin/python scripts/ingest/import_public_repositories.py
.venv/bin/python scripts/ingest/expand_repository_fields.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/ingest/discover_official_pages.py --priority 2 --resume
.venv/bin/python scripts/ingest/import_confirmed_homepages.py
.venv/bin/python scripts/ingest/research_all_schools.py --resume
.venv/bin/python scripts/ingest/apply_context_corrections.py
.venv/bin/python scripts/ingest/import_research_claims.py
.venv/bin/python scripts/ingest/sync_source_candidates.py
```

范围构建校验官方附件哈希，也支持本地附件。社区导入按[仓库清单](data/external/repositories.yaml)锁定上游提交；只读数据，不执行上游代码。采集结果会随网站变化，详见[采集说明](docs/source-collection.md)。采集完成后重新执行生成与校验命令。可选的 `validate_profiles.py --release` 专供未来人工审定版本使用，本轮验收使用 `--automatic-draft`。

视觉文件检查需要`requirements-research.txt`中的Pillow。只重试解析/访问失败的视觉文件可运行`.venv/bin/python scripts/ingest/expand_repository_fields.py --retry-visual-errors`，再重新生成视图、索引和覆盖报告。

## 来源与许可

学校官网、教育部门及校方提交的招生资料优先。公开 GitHub 数据按完整校名匹配到教育部标识码，记录来源类型、上游版本和日期。社区英文名不自动等同现行官方译名；社区配色仅写入资源参考，官方 VI 标准色、标识取样建议色分别标记方法。访问失败会尝试不同域名或页面入口，仍失败时保留记录，不能将其写成“学校没有”。

原创脚本按 [MIT](LICENSE)，原创数据整理按 [CC BY 4.0](LICENSE-DATA.md)。[第三方数据说明](data/external/README.md)列出独立许可；本库许可不替学校或社区作者授权校徽、字体、照片与模板。贡献方法见[贡献指南](CONTRIBUTING.md)。

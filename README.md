# 高校 PPT 资料库

为个人和 AI 助手制作高校主题 PPT 整理可检索的学校事实、视觉线索和资源入口。

**当前范围：教育部 2026 年名单中的全部 1,412 所本科院校，均已建档。** 含普通本科、职业本科、民办与合作办学院校；不再采用旧版 933 所选校过滤。资料持续自动补采，本轮不要求人工签核。建档数量与字段覆盖率分别统计，见[覆盖率报告](docs/coverage-2026.md)。

## 找学校与资料

1. 在[总索引](indexes/catalog.csv)按校名、学校标识码、地区查找，也可浏览[地区](indexes/by-province.csv)、[类别](indexes/by-category.csv)、[标签](indexes/by-tag.csv)、[状态](indexes/by-status.csv)。
2. 打开索引中的 `profile_path`，读取唯一事实源 `profile.yaml`。`OFFICIAL.md` 展示官方 PPT 入口；有社区资源的学校另有 `COMMUNITY.md`，包含 Beamer、Marp 和校徽参考入口。
3. 每字段先看 `availability`、`source`、`verified`、`checked_at`。自动采集标记为 `auto`，可按来源和用途使用；冲突、未调查和检索后未找到均显式保留。

示例：[清华大学](universities/北京市/4111010003/profile.yaml)、[北京大学](universities/北京市/4111010001/profile.yaml)、[西湖大学](universities/浙江省/4133014626/profile.yaml)。PPT 和 AI 助手的完整使用方法见[数据指南](docs/data-guide.md)。

## 分类和层级

```text
universities-index.csv                  教育部普通高校原表：2952 所，含专科
data/universities-scope-2026.csv        本科范围：1412 所，唯一范围表
data/source-manifest.yaml              官方附件、哈希、范围与采集政策
data/external/                         已匹配的许可数据子集、上游版本和许可
data/review/                           检索台账、候选、来源差异与补采队列
universities/<省级地区>/<学校标识码>/
   profile.yaml                        单校唯一事实源
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
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/report_research.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/validate/validate_profiles.py --automatic-draft
.venv/bin/python scripts/ingest/build_indexes.py --check
.venv/bin/python scripts/ingest/render_official.py --check
.venv/bin/python scripts/ingest/render_community.py --check
.venv/bin/python -m unittest discover -s scripts/validate -p 'test_*.py'
```

联网补采流程：

```bash
.venv/bin/python scripts/ingest/build_2026.py
.venv/bin/python scripts/ingest/seed_profiles.py --all
.venv/bin/python scripts/ingest/collect_wikidata_candidates.py
.venv/bin/python scripts/ingest/import_public_repositories.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/ingest/discover_official_pages.py --priority 2 --resume
.venv/bin/python scripts/ingest/import_confirmed_homepages.py
.venv/bin/python scripts/ingest/research_all_schools.py --resume
.venv/bin/python scripts/ingest/apply_context_corrections.py
.venv/bin/python scripts/ingest/import_research_claims.py
.venv/bin/python scripts/ingest/sync_source_candidates.py
```

范围构建校验官方附件哈希，也支持本地附件。社区导入按[仓库清单](data/external/repositories.yaml)锁定上游提交；只读数据，不执行上游代码。采集结果会随网站变化，详见[采集说明](docs/source-collection.md)。采集完成后重新执行生成与校验命令。可选的 `validate_profiles.py --release` 专供未来人工审定版本使用，本轮验收使用 `--automatic-draft`。

## 来源与许可

学校官网、教育部门及校方提交的招生资料优先。公开 GitHub 数据按完整校名匹配到教育部标识码，记录来源类型、上游版本和日期。社区英文名不自动等同现行官方译名；社区配色仅写入资源参考，官方 VI 标准色、标识取样建议色分别标记方法。访问失败会尝试不同域名或页面入口，仍失败时保留记录，不能将其写成“学校没有”。

原创脚本按 [MIT](LICENSE)，原创数据整理按 [CC BY 4.0](LICENSE-DATA.md)。[第三方数据说明](data/external/README.md)列出独立许可；本库许可不替学校或社区作者授权校徽、字体、照片与模板。贡献方法见[贡献指南](CONTRIBUTING.md)。

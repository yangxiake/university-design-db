# 高校 PPT 资料库

为个人和 AI 助手制作高校主题 PPT 整理可追溯的学校事实、视觉线索与官方资源入口。

**状态：资料整理与人工复核中，尚未正式发布。** 2026 年范围表覆盖 933 所，单校档案正在从官网补充，准确进度见[覆盖率报告](docs/coverage-2026.md)。不要把范围数量当成资料完成数量，也不要将自动提取字段当作人工确认事实。

## 找学校

1. 在 [总索引](indexes/catalog.csv) 按校名、教育部学校标识码或省级地区查找；可用 [地区](indexes/by-province.csv)、[筛选类别](indexes/by-category.csv)、[重叠标签](indexes/by-tag.csv)、[资料状态](indexes/by-status.csv) 浏览。
2. 若总索引中的 `profile_path` 非空，打开对应 `profile.yaml`；这是单校事实源。空值表示尚未建档。`OFFICIAL.md` 是由档案生成的官方 PPT 资源便读视图。
3. 仅使用有明确来源、核查日期且标为 `verified: human` 的学校事实。`unresearched` 表示尚未调查，`not_found` 表示记录过检索仍未找到，`conflict` 表示来源不一致。

例如：[清华大学档案](universities/北京市/4111010003/profile.yaml)、[北京大学档案](universities/北京市/4111010001/profile.yaml)、[西湖大学档案](universities/浙江省/4133014626/profile.yaml)、[燕京理工学院档案](universities/河北省/4113013895/profile.yaml) 展示不同学校类型、来源与冲突的记录方式，当前仍待人工复核。

## 仓库层级

```text
universities-index.csv             教育部 2026 年普通高校 Tier 0，总计 2952 所
data/universities-scope-2026.csv  深加工范围，933 所
data/source-manifest.yaml         来源网址、附件哈希、范围输入
data/selection-source/           原始选校表，供重建范围
data/review/                     自动检索候选线索，不是发布事实
universities/<省级地区>/<学校标识码>/  已开始调查的学校才建档
  profile.yaml                   单校唯一事实源
  OFFICIAL.md                    官方资源的生成视图
indexes/                         派生的检索索引
docs/                            需求、字段、使用与覆盖率说明
scripts/                         重建、渲染、校验脚本
```

省级分组取自教育部原表；标识码仅作为身份键，不从前几位反推当前省份。教育部空备注不等于“公办”。筛选类别只说明纳入规则，详情见 [需求](docs/requirements.md)。

## 本地生成与校验

需 Python 3.9+。在仓库根目录运行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/validate/validate_profiles.py
.venv/bin/python scripts/ingest/build_indexes.py --check
.venv/bin/python scripts/ingest/render_official.py --check
.venv/bin/python -m unittest discover -s scripts/validate -p 'test_*.py'
```

更新范围和逐校资料时，另运行以下联网采集流程；官网访问结果会随时间变化，不能替代上面的本地校验：

```bash
.venv/bin/python scripts/ingest/build_2026.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/ingest/discover_official_pages.py --priority 2 --resume
.venv/bin/python scripts/ingest/extract_official_excerpts.py
.venv/bin/python scripts/ingest/import_confirmed_homepages.py
.venv/bin/python scripts/ingest/import_curated_founding.py
.venv/bin/python scripts/ingest/import_direct_founding.py
.venv/bin/python scripts/ingest/import_explicit_mottos.py
.venv/bin/python scripts/ingest/import_curated_priority.py
.venv/bin/python scripts/ingest/extract_visual_color_leads.py
.venv/bin/python scripts/ingest/import_visual_entries.py
.venv/bin/python scripts/ingest/import_curated_visual.py
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/build_review_queue.py
```

范围脚本校验教育部附件哈希；也支持 `--moe-xls` 与 `--double-first-pdf` 传入本地附件。开始调查新学校时可用 `seed_profiles.py --school-code <标识码>` 建立单校草稿，不覆盖已有档案。正式发布时还须运行 `validate_profiles.py --release`，其人工复核门槛目前预期不会通过。

## 来源与使用范围

教育部原始名单及双一流附件的链接、哈希见 [来源清单](data/source-manifest.yaml)。[逐校复核队列](data/review/review-queue-2026.csv) 把 933 所范围、档案状态和候选线索排在一起，双一流 144 所优先。[Wikidata 候选表](data/review/wikidata-candidates-2026.csv) 仅帮助定位资料，不作为单校事实直接使用。[官网入口补充表](data/review/official-site-overrides-2026.csv) 记录搜索到的学校站点和证据入口；自动标题匹配仍需人工检查。

[视觉色值线索表](data/review/visual-color-leads-2026.csv) 只保存页面中的数字候选，不直接认定为学校标准色。[逐校色值判读](data/review/official-color-decisions-2026.yaml) 记录官网或校方 VI 手册、原 RGB/HEX 与用途口径；同一官网内的数值冲突留在单校档案的 `candidates` 中。数字颜色仅占少数学校，其余不可从校徽图片或网页 CSS 猜测为官方主题色。

[首批官网事实判读](data/review/priority-official-facts-2026.yaml) 为此前缺档的双一流高校补充官网入口、校训、部分建校年和标识入口，逐字段保留原页；南京师范大学目前仅定位官网首页，校训仍待本校页面核对。

原创脚本按 [MIT](LICENSE)；本仓库原创的数据整理、分类与简短说明按 [CC BY 4.0](LICENSE-DATA.md)。学校发布的文字、校名校徽、模板、照片、字体和链接目标遵循各权利人的规则；本仓库的许可不会替学校授权这些材料。

采集与核查边界见[官网资料采集说明](docs/source-collection.md)。修订资料请读 [贡献指南](CONTRIBUTING.md)；PPT 与 AI 助手使用请读 [数据指南](docs/data-guide.md)。

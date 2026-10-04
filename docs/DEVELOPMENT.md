# 开发与数据维护

本页是 University Design DB 的维护入口。使用者从[在线目录指南](viewer-guide.md)或[数据指南](data-guide.md)开始；字段与证据口径见[Schema](schema.md)和[来源核查说明](source-collection.md)。

## 环境与统一检查

Python 3.9+；网页测试使用 Node.js 24，无 npm 依赖。`requirements-quality.txt` 包含生成、图像解析和 JSON Schema 校验所需 Python 依赖。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/check.py
```

Node 不在 PATH 时用 `scripts/check.py --node /path/to/node` 指定。检查验证现有数据、七项派生内容、Python 与网页测试、格式和仓库文件不变性，不联网采集。检查期间不要编辑仓库文件。关卡与 CI 矩阵见[质量检查](quality-checks.md)。

## 事实源与修改顺序

1. 用 `data/universities-scope-2026.csv` 和学校标识码确认身份。当前全部 1,412 所本科院校已有 v4 档案。
2. 修改对应 `profile.yaml`，保留直接来源、来源类型、检查日期、方法和不确定状态。人工复核规则见[贡献指南](../CONTRIBUTING.md)。
3. 重建派生视图和索引；不手改单校 Markdown、CSV / JSONL 或 `viewer/data/`。
4. 资料变动时更新覆盖报告与队列，然后执行统一检查。
5. PR 说明身份、来源、变更与实际验证。版本变化记入 [CHANGELOG](../CHANGELOG.md)，采集台账留在 `data/review/`。

当前约束为 `data/profile-schema-v4.yaml` / `.json`；v2 / v3 保留用于历史版本与兼容测试。演示导出使用独立的 `data/ppt-export-schema-v1.json`。身份范围更新先维护来源清单与标识码关系；字段更新不静默改变年度名单身份。

## 重建派生资料

按依赖顺序运行七项生成器：

```bash
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/render_enriched.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/ingest/build_ppt_indexes.py
.venv/bin/python scripts/ingest/build_ppt_profiles.py
.venv/bin/python scripts/ingest/build_viewer.py
```

前三项生成单校便读视图及完整事实索引；后续生成分类索引、既有演示索引、精简导出和网页分包。统一检查对七项使用 `--check` 比较已有文件，不自动修补。

资料更新后按变更内容生成报告：

```bash
.venv/bin/python scripts/validate/report_ppt_core.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/build_review_queue.py
```

报告日期是执行日期。主字段覆盖不等于视觉审定或全部可选资料完备。来源映射、视觉补采等专项报告见[文档目录](README.md)。仅修改文档或门面时不重写学校事实和数据报告。

## 采集、导入与来源审计

按[主字段范围](../data/ppt-core-fields.yaml)与[缺口队列](../data/review/ppt-core-queue-2026.csv)选择目标。详细采集器、导入条件、文件读取与证据重放见[来源采集说明](source-collection.md)。

```bash
.venv/bin/python scripts/ingest/collect_ppt_core.py --resume --collect-only
.venv/bin/python scripts/ingest/collect_ppt_core.py --import-only
```

`--collect-only` 产生回执与候选，`--import-only` 写入符合条件的事实；采集成功不等于人工签核。其他独立流程见[其他主字段来源与文件重试](source-collection.md#其他主字段来源与文件重试)。不重新运行历史全字段扩展、招生、统计或就业采集流程。

来源审计检查发布主体、现行完整校名、原文主语、版本和日期、颜色角色、文件格式、容器与成员哈希、独立使用条件。冲突不自动择一；链接发现不继承附件已读状态。第三方资料按[固定上游清单](../data/external/repositories.yaml)及[许可说明](DATA-LICENSE.md)处理。原文件缓存位于忽略目录，不随源码或资料包发布。

## 网页构建与发布

网页是原生 HTML / CSS / JavaScript 模块，没有框架或包管理构建配置。生成后的网页数据已提交；静态站点构建只需 Python 标准库：

```bash
python3 scripts/build_pages.py --output-dir tmp/pages-development/university-design-db
python3 -m http.server 8766 --bind 127.0.0.1 --directory tmp/pages-development
```

打开 <http://127.0.0.1:8766/university-design-db/>。输出目录须是 `tmp/` 内的空目录。产物包含固定网页文件、目录与 31 个地区 JSON、`.nojekyll`、`deployment.json`；档案和文档链接指向构建源提交。

main 推送由 Actions 先运行 Python 3.9 / 3.13 检查，再构建、上传 Pages artifact 并部署。Pages Source 使用 GitHub Actions。`scripts/publish_pages.py` 是历史分支发布工具，不参与当前发布。流程与权限见[GitHub Pages](github-pages.md)。

资料包使用 `scripts/package_ppt_release.py --version <真实版本>`，要求已检查的干净提交，内含资料、网页、许可和逐文件哈希，不附第三方图形、模板、字体或缓存。只有实际创建的 tag / Release 才写入已发布记录；未发布变化留在 CHANGELOG 的未发布部分。

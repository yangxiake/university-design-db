# 贡献与复核

欢迎纠正来源、补充官方资料或提交单校复核记录。请先用 `indexes/catalog.csv` 确定学校标识码；若该校尚无档案，运行 `.venv/bin/python scripts/ingest/seed_profiles.py --school-code <标识码>`，再修改唯一的 `profile.yaml`。不要手改索引、`OFFICIAL.md` 或 `COMMUNITY.md`。

正向事实优先使用学校官网、学校章程、官方 VI 和官方资源页；教育部名单仅支撑其原有列。社区数据可补充带明确版本和来源类型的事实；不得把社区信息称为学校官方声明。提交时填写短事实、直接来源 URL、访问日期和适当的历史或取色方法。无法找到的字段记检索入口与日期；互相矛盾的来源记录候选值。请勿复制学校整篇介绍或上传校徽、字体、照片、模板文件。

人工复核者须亲自打开来源、确认页面所说内容与字段口径一致、查看官方资源适用对象与使用规则，再把相关字段的 `verified` 改成 `human`。一校核查完毕后设置 `research.status: reviewed`、`checked_at` 和 `reviewed_by`。提交者不得将仅由 AI 自动提取的内容标成人工复核。

修改后运行：

```bash
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/validate/validate_profiles.py --automatic-draft
.venv/bin/python scripts/ingest/build_indexes.py --check
.venv/bin/python scripts/ingest/render_official.py --check
```

本轮自动采集版本无需人工签核。`validate_profiles.py --release` 保留为未来人工审定版本的可选检查。年度教育部名单变更时先更新 `source-manifest.yaml` 和构建脚本，再维护学校标识码的延续关系；不得把旧年度名称、地区或办学性质静默覆盖成新年度事实。

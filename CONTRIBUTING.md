# 贡献与复核

欢迎纠正来源、补充官方资料或提交单校复核记录。请先用`indexes/catalog.csv`确定学校标识码；若该校尚无档案，运行`.venv/bin/python scripts/ingest/seed_profiles.py --school-code <标识码>`创建v3档案，再修改唯一的`profile.yaml`。不要手改派生索引、PROFILE/VISUAL/OFFICIAL/COMMUNITY视图或profiles.jsonl。

正向事实优先使用学校官网、学校章程、官方 VI 和官方资源页；教育部名单仅支撑其原有列。社区数据可补充带明确版本和来源类型的事实；不得把社区信息称为学校官方声明。提交时填写短事实、直接来源 URL、访问日期和适当的历史或取色方法。无法找到的字段记检索入口与日期；互相矛盾的来源记录候选值。请勿复制学校整篇介绍或上传校徽、字体、照片、模板文件。

人工复核者须亲自打开来源、确认页面所说内容与字段口径一致、查看官方资源适用对象与使用规则，再把相关字段的 `verified` 改成 `human`。一校核查完毕后设置 `research.status: reviewed`、`checked_at` 和 `reviewed_by`。提交者不得将仅由 AI 自动提取的内容标成人工复核。

先安装`requirements-quality.txt`。修改后运行：

```bash
.venv/bin/python scripts/ingest/render_official.py
.venv/bin/python scripts/ingest/render_community.py
.venv/bin/python scripts/ingest/render_enriched.py
.venv/bin/python scripts/ingest/build_indexes.py
.venv/bin/python scripts/ingest/build_ppt_indexes.py
.venv/bin/python scripts/ingest/build_ppt_profiles.py
.venv/bin/python scripts/validate/report_field_union.py
.venv/bin/python scripts/validate/report_coverage.py
.venv/bin/python scripts/validate/build_review_queue.py
.venv/bin/python scripts/check.py
```

本轮自动采集版本无需人工签核。`validate_profiles.py --release` 保留为未来人工审定版本的可选检查。年度教育部名单变更时先更新 `source-manifest.yaml` 和构建脚本，再维护学校标识码的延续关系；不得把旧年度名称、地区或办学性质静默覆盖成新年度事实。

新增字段按`data/profile-schema-v3.yaml`维护类型和来源口径，同时更新`data/profile-schema-v3.json`及自定义语义校验。PPT导出字段另由`data/ppt-export-schema-v1.json`约束。提交时GitHub Actions会校验数据和派生文件，检查本身不修补事实。社区校徽要给具体文件URL、学校身份、版本、访问状态及独立图形许可；素材不上传。排名、招生、就业与人数/面积不能丢掉年份、地区或统计口径。社区取色记community_logo_sample，不能填写成official_vi。兼容数据子集保留原LICENSE；快照及其派生字段同样遵循上游许可。

# 贡献指南

University Design DB 接受资料纠错、来源更新和代码改进。当前范围为教育部 2026 年名单中的 1,412 所本科院校，档案结构为 v4。先按[总索引](indexes/catalog.csv)确认学校标识码，避免把母校、院系、前身或同名学校的资料混在一起。

## 报告问题

在 [Issues](https://github.com/yangxiake/university-design-db/issues) 报告错误校名、错误校徽、过期标识、错误配色、失效 URL 或官方来源变化。请提供：

- 学校全名、标识码，以及有问题的字段、文件或页面地址。
- 当前记录、建议更正内容与原始来源 URL；涉及版本变化时说明发布单位和日期。
- 链接失效时注明访问日期和看到的结果；网页问题提供复现步骤和浏览器。

不必先准备代码 PR。来源不充分时可以只提交线索，资料保持待核验状态。

## 新增或更新资料

修改 `universities/<省级地区>/<学校标识码>/profile.yaml`。这是单校唯一事实源；便读视图、CSV / JSONL、索引与 `viewer/data/` 通过生成器更新，操作见[开发指南](docs/DEVELOPMENT.md)。当前范围内全部学校已有档案；新增学校身份或更换年度名单应先在 Issue 中说明范围与标识码延续关系。

- 尽量提供原始发布页或文件 URL，注明校方、主管部门、第三方项目或社区来源，保留检查日期与可取得的版本、哈希。
- 不只提交来源不明的图片；校徽、字体、照片、模板和整篇学校介绍不上传到仓库。提交入口、必要元数据和简短事实。
- 标识须对应现行学校身份。旧名、前身、母校图形和未宣布采用的征集稿不能充当当前学校标识。
- 配色说明依据与用途：`official_vi` 必须有校方数字规范证据；图形取色、网页 CSS、社区主题作为设计参考。印刷色不擅自换算为官方屏幕值。
- 建校年注明前身起点、创办、合并或更名等口径。英文名与简称保留发布主体和适用时期。
- 冲突资料保存候选、来源和差异，不猜一个答案。访问失败保留回执；`not_found` 需要实际检索入口和日期，不能代表永久不存在。
- 第三方数据子集及其派生字段继续遵循上游许可；仓库代码许可不代替图形授权。见[数据许可](docs/DATA-LICENSE.md)和[第三方来源](data/external/README.md)。

字段以[当前 Schema](docs/schema.md)、[v4 约束](data/profile-schema-v4.json)和[字段范围](data/ppt-core-fields.yaml)为准。新增字段先说明视觉或演示用途，再同步 Schema、语义校验与相关导出。招生、排名、就业、人数、面积等不在当前范围内。

## 人工复核

亲自打开来源，核对学校身份、事实口径、标识版本、色值方法与资源适用范围后，才能将相应事实的 `verified` 改为 `human`。仅由 AI 提取或自动检查的资料保持 `auto`。

只有完成整校复核后才设置 `research.status: reviewed`，并填写检查日期与 `reviewed_by`。部分字段复核不等于整校签核。`validate_profiles.py --release` 是人工审定版本的额外门槛，普通资料更新使用统一自动资料检查。

## 代码与 PR

从当前 main 创建分支，提交聚焦的修改。PR 说明问题、最终变化和实际执行的验证；资料变动列出学校标识码与直接来源。

需要 Python 3.9+ 和 Node.js 24，无 npm 依赖。在仓库根目录初始化环境并检查：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/check.py
```

资料修改后先按[开发指南](docs/DEVELOPMENT.md)重建相关派生文件和覆盖报告，再运行检查。网页或构建代码变化时还运行：

```bash
.venv/bin/python scripts/build_pages.py --output-dir tmp/pages-pr-check
```

输出目录必须为空；重复运行时换用新的 `tmp/` 子目录。预览与项目子路径验证见[Pages 说明](docs/github-pages.md)。

GitHub Actions 对 PR 运行离线质量检查；main 推送还会在两套 Python 检查通过后构建、部署 Pages。关卡见[质量检查](docs/quality-checks.md)。检查通过表示结构和规则一致，不表示资料全量完备、图形均为现行正式版本或素材已获授权。

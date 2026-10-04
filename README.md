# University Design DB

中国高校校徽、配色、视觉规范与演示素材的开放资料库。

**[打开在线目录](https://yangxiake.github.io/university-design-db/)** · [数据使用指南](docs/data-guide.md) · [贡献指南](CONTRIBUTING.md) · [版本记录](CHANGELOG.md)

## 为什么整理这些资料

高校的校徽、标准色、校名标识、VI（Visual Identity）和演示模板，常常分散在学校官网、宣传部门、新闻中心、院系网站、PDF 附件、公开下载页和社区项目中。找到文件后，还需要判断版本、核对色值依据，并区分校方发布与社区整理；同一学校的不同页面也可能给出互相矛盾的资料。

University Design DB 将与高校视觉设计和演示制作有关的公开资料整理为可检索、可追溯、可继续核验的结构化记录。资料保留原始来源、检查日期和不确定状态，便于使用者回到出处判断用途。

## 在线目录

[在线目录](https://yangxiake.github.io/university-design-db/)无需下载仓库或安装环境，可以：

- 按中文校名、带来源的中英文别名或学校标识码搜索，结合地区、素材类型及来源等条件筛选。
- 查看校徽、校名文字和徽名组合，切换文件版本，查看格式、透明背景、读取记录及原始出处。
- 查看校方数字色、仅印刷色和设计参考色，展开取值依据，复制已有的 HEX 色值。
- 打开官方或社区的 PPT、VI 与视觉文件入口，查看已读取 PPTX 的结构信息。
- 查看单校资料，复制或下载 JSON，分享保留学校和筛选条件的地址。

图形从原来源加载，网络或原站限制可能影响预览。ZIP 成员和 PDF 内嵌标识提供原文件入口及定位信息；目录不提供 PPT 逐页渲染。操作和状态说明见[在线目录使用指南](docs/viewer-guide.md)。

## 可查资料

| 资料 | 内容 |
| --- | --- |
| 学校身份 | 中文与英文校名、学校标识码、省市、官网及带来源的简称、别名 |
| 学校标识 | 校徽、Wordmark / 校名文字、徽名组合及逐文件来源与格式信息 |
| 配色 | 校方公布的数字色和印刷色、标识取色或社区设计参考、冲突候选与取值依据 |
| 视觉与演示资源 | 官方 VI、视觉文件、学校或院系 PPT 入口、社区 Beamer / Marp 等主题 |
| 演示用基础资料 | 建校年及历史起点口径、校训、由学校身份生成的短简介等少量字段 |
| 来源与状态 | 来源类型、检查日期、自动或人工核对标记、文件读取记录、版本和取得时的哈希 |

字段有记录不代表已经人工审定，资源入口也不代表文件已经读取或获得使用授权。详细字段见[数据结构](docs/schema.md)。

## 覆盖与项目状态

范围以[教育部 2026 年普通高校名单](https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A03/202606/t20260618_1441074.html)中 `level=本科` 的记录为准，包含普通本科、职业本科、民办与合作办学院校，共 **1,412 所**，分布于 31 个省级分组。专科院校和名单外军校不纳入当前单校档案范围。

以下数量由当前档案及其导出核对，按学校计数：

| 状态 | 学校数 | 含义 |
| --- | ---: | --- |
| 已建身份档案 | 1,412 | 每校一份 v4 `profile.yaml`，与本科范围表逐一对应 |
| 已记录英文校名 | 1,411 | 有来源记录，包含校方与社区来源 |
| 已记录建校年及口径 | 1,412 | 保留前身、创办等历史起点依据 |
| 至少一个标识文件已读取 | 1,383 | 文件内容已检查，来源可能为校方或社区 |
| 其中至少一个校方来源标识已读取 | 1,023 | 校方发布身份与现行版本、图形授权仍须分别判断 |
| 已选择有依据的屏幕主色 | 1,383 | 73 所为校方数字主色，1,310 所为设计参考 |
| 整校人工签核 | 0 | 当前全部档案的调查状态为 `auto_collected` |

按现有[演示主字段规则](data/ppt-core-fields.yaml)，1,380 所具备英文名、建校年、已读取标识和可用屏幕主色；32 所仍有 59 项缺口。这只衡量该组字段，不表示 VI、模板或其他资料全部收集完成，也不表示逐校视觉审定完成。

缺失、待解释、不可访问、冲突和未核验的资料可以保留，这是来源管理的一部分。字段的实际状态为 `unresearched`、`not_found`、`conflict`、`found`，核对与访问状态另列。逐字段统计见[主字段覆盖](docs/ppt-core-coverage-2026.md)、[完整覆盖报告](docs/coverage-2026.md)和[导出覆盖数据](indexes/ppt-profiles-coverage.json)。

## 来源与核验

视觉资料优先查阅学校官方网站、校方正式 VI 文件，以及校方发布的 PDF、附件和宣传资料；学校身份与范围以教育主管部门公开资料为依据。直接来源不足时，使用可追溯的公开项目和社区资源，并保留来源类型、固定版本或检查日期。

各项证据分别记录，不能统称为“已验证”：

| 判断 | 查看什么 |
| --- | --- |
| URL 当时可以访问 | 来源访问回执与检查日期；不保证持续可用 |
| 文件可以取得、格式已检查 | `access_status`、`download_status`、文件元数据；`content_inspected` 表示实际读取内容 |
| 来源属于校方 | `source`、`source_type`、资源的 `official` 标记及学校身份依据 |
| 标识为现行正式版本 | 原发布说明、版本和适用范围；文件可读不能单独证明这一点 |
| 色值来自校方规范 | `method=official_vi` 及原数字证据；取样、网页 CSS 与社区主题另作参考 |
| 事实经过人工核对 | `verified=human` 及复核记录；`auto` 是自动核对，`unverified` 是未核对 |

仅有 CMYK / Pantone 的印刷色保留空的屏幕值；RGB 与 HEX 矛盾时保留候选。社区项目经过整理，不会因此变成学校官方发布。查阅失败或检索未找到，也不能推断学校没有该资料。规则见[来源采集与核查说明](docs/source-collection.md)。

## 数据组织

```text
universities/<省级地区>/<学校标识码>/
├── profile.yaml     单校结构化资料的主要事实源
├── PROFILE.md       便读档案
├── VISUAL.md        标识、配色与视觉资源
├── OFFICIAL.md      官方演示资源
└── COMMUNITY.md     有社区资源时生成
```

学校标识码用于关联资料。CSV、JSONL、分类索引和网页数据由档案派生，不建立重复的单校事实副本。

- [`data/`](data/)：本科范围、Schema、来源清单、第三方许可子集与检索记录。
- [`indexes/catalog.csv`](indexes/catalog.csv)：单校路径与检索入口；另有地区、类别、标签和状态索引。
- [`indexes/profiles.jsonl`](indexes/profiles.jsonl)：完整档案的程序读取格式。
- [`indexes/ppt-profiles.jsonl`](indexes/ppt-profiles.jsonl) / [CSV](indexes/ppt-profiles.csv)：适用于演示制作的精简导出，可用于程序、自动化处理或 AI 上下文。
- [`viewer/`](viewer/)：静态在线目录；[`docs/`](docs/README.md)：使用、维护和历史记录；[`scripts/`](scripts/)：导入、生成、检查与构建工具。

示例：[清华大学](universities/北京市/4111010003/profile.yaml)、[北京大学](universities/北京市/4111010001/profile.yaml)、[西湖大学](universities/浙江省/4133014626/profile.yaml)。读取方式见[数据指南](docs/data-guide.md)与[演示数据导出说明](docs/ppt-export-v1.md)。

## 本地使用

下载仓库后，在根目录运行：

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

打开 <http://127.0.0.1:8765/viewer/>。浏览目录只需 Python 提供静态 HTTP 服务；图形预览和原资源下载仍可能需要网络。

## 开发与维护

检查和数据生成使用 Python 3.9+；网页规则测试使用 Node.js 24，没有 npm 依赖。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/check.py
```

统一检查验证现有数据、Schema、测试和派生文件一致性，不联网采集。GitHub Actions 对推送和 PR 运行 Python 3.9 / 3.13 检查；main 更新后先检查，再构建并部署 Pages。

详细操作见[开发指南](docs/DEVELOPMENT.md)、[质量检查](docs/quality-checks.md)与[Pages 部署](docs/github-pages.md)。报告资料错误或提交 PR 见[贡献指南](CONTRIBUTING.md)；版本变化见[CHANGELOG](CHANGELOG.md)。

## 项目边界

项目围绕高校视觉设计、演示文稿、学校品牌素材和视觉资料检索。建校年等基础字段服务于这些用途；当前不维护完整高校百科，也不持续收集招生分数、排名、就业率、在校人数、校园面积、联系电话、完整学科数据库或新闻资讯。

## 许可证

| 内容 | 许可 |
| --- | --- |
| 原创代码（`scripts/` 与 `viewer/`） | [MIT License](LICENSE) |
| 原创数据整理、分类、索引与简短说明 | [CC BY 4.0](docs/DATA-LICENSE.md) |
| 第三方数据子集 | 保留[上游许可与来源](data/external/README.md) |
| 学校校徽、字体、照片、PPT、VI 文件、模板等第三方素材 | 遵循原权利人的版权与许可条件 |

本项目的 MIT 或 CC BY 4.0 不会自动重新授权第三方素材。归属、署名和使用边界见[数据许可说明](docs/DATA-LICENSE.md)。

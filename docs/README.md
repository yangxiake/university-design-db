# 文档目录

University Design DB 的定位与入口见[仓库首页](../README.md)。当前学校事实以单校 `profile.yaml` 为准；使用、维护和历史记录分别列在下方。

## 使用与数据

| 文档 | 用途 |
| --- | --- |
| [在线目录指南](viewer-guide.md) | 搜索、筛选、预览、配色与单校 JSON |
| [结构化资料指南](data-guide.md) | 读取顺序、来源判断与程序 / AI 使用边界 |
| [演示资料指南](ppt-guide.md) | 标识、配色、模板与视觉资源分类 |
| [精简导出 v1](ppt-export-v1.md) | JSONL / CSV 结构、选择规则和查询示例 |
| [数据结构 v4](schema.md) | 当前分组、事实封套与状态含义 |
| [主字段覆盖](ppt-core-coverage-2026.md) / [完整覆盖](coverage-2026.md) | 建档、文件已读和字段完备分别统计 |
| [剩余主字段清单](core-completion-remaining-2026.md) | 最近资料批次的逐校缺口与证据限制 |

## 维护与贡献

| 文档 | 用途 |
| --- | --- |
| [开发指南](DEVELOPMENT.md) | 环境、生成、报告、来源审计与构建 |
| [贡献指南](../CONTRIBUTING.md) | 报错、资料更新、人工复核和 PR |
| [来源采集](source-collection.md) | 采集器、导入条件、判读与文件读取 |
| [质量检查](quality-checks.md) | 离线关卡、CI 与已有测试记录 |
| [GitHub Pages](github-pages.md) | 当前 Actions 发布与本地预检 |
| [数据许可](DATA-LICENSE.md) / [第三方来源](../data/external/README.md) | 原创整理与上游资料的独立许可 |
| [版本记录](../CHANGELOG.md) | 未发布变化及真实版本摘要 |

## 历史批次与证据

历史报告保存当时的范围、覆盖数字、计划和检查结果，不替代当前档案。私有仓库、未启用 Pages、v3 全字段或 933 所范围等叙述须按文档日期理解；当前仓库公开，档案范围为 1,412 所，Pages 使用 Actions。

- [字段需求](requirements.md)：当前字段边界与发布条件。
- [2026-10-03 计划](next-phase-plan-2026.md)与[交接记录](handoff-2026-10-03.md)：开发过程快照。
- [逐校访查](research-progress-2026.md)与[来源映射](github-field-union-2026.md)：来源、字段和检索统计。
- [官方视觉补采](visual-completion-progress-2026.md)、[视觉缺口补采](visual-gap-progress-2026.md)、[M4 第一批](m4-batch01-progress-2026.md)、[M4 第二批](m4-batch02-progress-2026.md)：批次基线、增量与逐校记录。
- [`releases/`](releases/)：版本详细说明与当时验证证据，摘要集中在 CHANGELOG。
- [`data/review/`](../data/review/README.md)：来源访问、候选、判读、冲突和复核队列。历史回执不自动覆盖当前资料。

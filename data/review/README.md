# 采集、差异与补采材料

本目录支撑来源追溯。单校事实只读取 `universities/<省级地区>/<学校标识码>/profile.yaml`；这里的候选、判读决定和队列不能代替单校档案。

| 层级 | 文件 | 用途 |
| --- | --- | --- |
| 入口候选 | `wikidata-*`、`official-site-overrides-*`、`official-page-discovery-*` | 找官网及主题页，记录访问和身份判断 |
| 页面调查 | `school-research-*.jsonl`、`narrative-leads-*.jsonl` | 短线索、读取状态、来源与哈希；包括排除记录 |
| 视觉候选 | `visual-color-leads-*`、`badge-palette-leads-*` | 数字候选及标识取色候选，尚未认定用途 |
| AI判读 | `*-decisions-*.yaml`、`priority-official-facts-*` | 逐字段导入依据，保留自动状态，人工核验可后续进行 |
| 差异记录 | `retracted-claims-*`、`research-claim-differences-*` | 撤回误匹配与已有资料差异 |
| 复核工作表 | `review-queue-*`、`school-research-status-*`、`field-research-status-*`、`page-visits-*` | 按校和字段定位来源、缺项、冲突及下一步 |

`official-color-decisions-*` 是校方公布的数字色值判读；`sampled-color-decisions-*` 是标注用途的PPT建议色。两者不混用。图片临时预览不随仓库分发，可按图片来源重新读取并比对哈希。

来源名称及正文主语决定证据属于哪所学校，不能只因页面位于某校域名就判为该校事实。判读文件保留历史研究记录；更正后的当前值以单校档案为准。

当前范围为1412所。`school-research-2026.jsonl`及本轮生成的状态表按全量范围维护；早先的followup台账、判读决定和原始选校记录可能只覆盖当时933所，保留其真实历史范围，不把历史缺行当作本轮学校缺档。`official-page-discovery`新增`attempted_urls`列记录本轮实际尝试的入口。`public-repository-differences`保存社区与已有值的差异。

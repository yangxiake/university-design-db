# 人和 AI 助手如何使用资料

1. 查 `indexes/catalog.csv`，按学校标识码打开 `profile_path`。全量本科已建档；更名、同名和独立学院身份以教育部原表及标识码区分。
2. 使用 `availability: found` 的资料，查看来源、时间及 `verified`。本轮资料主要为 `auto`，不要求先人工签核；在 PPT 备注或参考页保留来源，按实际证据表述。
3. `conflict` 保留多种来源值，暂停采用该字段；`unresearched` 和 `not_found` 不能说成“学校没有”。访问失败是采集状态，不是不存在的证据。
4. `source_type: community_dataset/community_directory` 的资料是社区记录，注意上游时间和现行名称。发生更名时优先找学校现行章程或英文官网。原始字段见`community.snapshots`所指的许可子集；社区与官方资料不同时保留来源差异，不覆盖已有学校事实。
5. 色值 `official_vi` 按 `basis` 区分标准色、辅助色、校徽色；RGB转HEX供屏幕使用，印刷按官方规范。`badge_sample/manual_derived/community_logo_sample` 标注为建议色；`community_theme`是社区主题参考色。完整配色位于`visual.color_palette`，不能因有HEX就当作官方标准；CMYK/Pantone空值不自行补造。
6. `PROFILE.md`供便读完整档案，`VISUAL.md`供逐文件校徽/校名与配色，`OFFICIAL.md`供官方PPT入口，`COMMUNITY.md`供社区主题。Beamer需要LaTeX，Marp采用Markdown/CSS，不应告诉用户它们是直接可编辑的PPTX。
7. 下载模板、字体、校徽前查看上游使用规则。本库只保留资料和入口，独立第三方数据许可见 `data/external/`。

## 给 AI 助手的简短指令

> 按学校标识码读档案，仅引用找到且有来源的字段，保留来源链接与历史起点。自动与社区资料如实标明出处；未调查、未找到、访问失败不能写成学校不存在该内容。配色明确区分官方VI、PPT建议色与社区主题色；不要补造校史或把社区主题认作学校官方模板。

字段数量、调查覆盖与尚待补采的内容见[覆盖率报告](coverage-2026.md)及[逐字段调查表](../data/review/field-research-status-2026.csv)。

## AI批量读取与素材选择

`indexes/profiles.jsonl`每行一校，是从`profile.yaml`生成的JSON全文；`indexes/enriched-catalog.csv`可先筛选哪些学校有校徽、配色、排名或学科记录。各表以`school_code`关联，不以简称作为唯一键。

选校徽时，先筛`visual.logo_assets.kind=badge`。`wordmark`是校名文字，不能假称校徽。`content_inspected`表示读到了文件结构，`indexed_not_fetched`仅表示历史资料提供了地址；文件名为.svg不保证内容是矢量。`vector/representation`、尺寸、透明信息不确定时为null；透明通道存在不表示整张图的背景已透明。独立图形许可与仓库代码许可分别查看。

画地图时，`coordinates.crs=unspecified`的社区点不能与WGS84/GCJ02精确坐标混用；这些点可表示近似分布，不表示学校全部校区。排名只能按同一publisher/ranking_name/year/scope比较，不能拼成无年份的“学校排名”。学科评估是按round与completeness标注的节选，不以空列表推断学校未参评。

录取参考必须同时带地区、年份、科类、批次和专业组口径。当前社区数据是2025重庆整理参考值，不能代替学校或考试院公布的实际录取数据；就业评论保留在社区快照中，不转成就业率或统计结论。

学生、教职工人数和校园面积必须带统计日期及口径；当前为空的字段表示尚无可导入来源，不表示0。

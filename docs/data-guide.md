# 人和 AI 助手如何使用资料

1. 查 `indexes/catalog.csv`，按学校标识码打开 `profile_path`。全量本科已建档；更名、同名和独立学院身份以教育部原表及标识码区分。
2. 使用 `availability: found` 的资料，查看来源、时间及 `verified`。本轮资料主要为 `auto`，不要求先人工签核；在 PPT 备注或参考页保留来源，按实际证据表述。
3. `conflict` 保留多种来源值，暂停采用该字段；`unresearched` 和 `not_found` 不能说成“学校没有”。访问失败是采集状态，不是不存在的证据。
4. `source_type: community_dataset` 的英文名是社区资料，注意上游时间和现行名称。发生更名时优先找学校现行章程或英文官网。社区不同值见来源差异表，不以社区数据覆盖已有学校事实。
5. 色值 `official_vi` 按 `basis` 区分标准色、辅助色、校徽色；RGB转HEX供屏幕使用，印刷按官方规范。`badge_sample` 与 `manual_derived` 标注“PPT建议色”。社区主题中的 `community_theme` 只作模板参考，不说成校方标准色。
6. `OFFICIAL.md` 供找官方 PPT 入口；`COMMUNITY.md` 供找社区主题、校徽参考及许可。Beamer 需要 LaTeX，Marp 采用 Markdown/CSS，不应告诉用户它们是直接可编辑的 PPTX。
7. 下载模板、字体、校徽前查看上游使用规则。本库只保留资料和入口，独立第三方数据许可见 `data/external/`。

## 给 AI 助手的简短指令

> 按学校标识码读档案，仅引用找到且有来源的字段，保留来源链接与历史起点。自动与社区资料如实标明出处；未调查、未找到、访问失败不能写成学校不存在该内容。配色明确区分官方VI、PPT建议色与社区主题色；不要补造校史或把社区主题认作学校官方模板。

字段数量、调查覆盖与尚待补采的内容见[覆盖率报告](coverage-2026.md)及[逐字段调查表](../data/review/field-research-status-2026.csv)。

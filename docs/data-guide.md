# 人和AI助手如何使用PPT资料

## 读取顺序

1. 从 `indexes/ppt-profiles.jsonl` 或配套CSV按 `school_code` 读取一校；范围是教育部1412所本科，军校不纳入。
2. 用 `identity` 识别学校，用 `logos` 取校徽/校名标识，用 `colors` 选择主题色，用 `content` 取建校年和校训，用 `templates` 查模板。
3. 完整主字段与可选校史见单校 `profile.yaml` / `PROFILE.md`；图形、色卡与VI见 `VISUAL.md`，官方和开源模板见 `OFFICIAL.md` / `COMMUNITY.md`。

## 必备与可选

学校身份、英文名、可读标识、附来源主色、建校年及口径是必备主字段；校训、辅色、VI、校史节点、校园意象、校花/吉祥物/校歌和模板是可选材料。缺口见[主字段覆盖](ppt-core-coverage-2026.md)，采集只按[主字段队列](../data/review/ppt-core-queue-2026.csv)推进。

招生、就业、排名、人数、面积、地址坐标、联系方式及学科统计已从现行数据剔除。简称与别名仅用于检索；短简介只从学校身份字段生成。

## 使用依据

- `availability=found` 才有正向事实；查看 `source`、`checked_at`、`verified`、`basis`。自动采集标为 `auto`，社区数据保留社区来源和固定版本。
- `conflict` 暂停自动采用；未调查、未找到和访问错误不能表述为学校没有该信息。不要为填满PPT编造年份、校训或官方英文译名。
- `official_vi` 才是校方数值标准；`badge_sample` / `manual_derived` 是PPT设计建议，`community_theme` / `community_logo_sample` 是社区参考。仅印刷CMYK/Pantone保留空HEX/RGB；有冲突时不换算择一。
- `badge`、`wordmark`、`combination` 分别表示校徽、校名文字、徽名组合；`site_identity` 的具体构成仍待确认。`content_inspected` 表示实际读取文件，文件后缀不能代替真实格式检查。
- `archive_member` 的URL是压缩包入口。先核对 `archive_sha256`，按原 `archive_member` 读取成员，再核对成员 `sha256`。`archive_member_display` 只为可读显示，不用于索引包内成员。
- 仓库代码许可与校徽、字体、模板授权分别查看。模板分学校通用、院系专用与社区主题；Beamer/Marp不是直接可编辑PPTX。

## 给AI助手的简短指令

> 按学校标识码读取PPT主字段，仅使用有来源的事实。校方发布、社区记录和设计建议分别标记；保留历史起点和颜色方法。缺资料时明确留空；不得虚构校训、年份、官方色值或授权。

查询命令和字段结构见[PPT精简导出v1](ppt-export-v1.md)。原创与第三方许可见[来源说明](../data/external/README.md)。

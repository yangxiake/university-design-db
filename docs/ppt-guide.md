# 为个人与AI助手制作PPT查资料

范围是教育部2026名单内1412所本科院校。学校标识码为唯一身份键，学校更名、校区与独立学院不能仅凭简称混用。

## 先找学校，再选素材

1. 在 [`indexes/ppt-starter.csv`](../indexes/ppt-starter.csv) 按完整学校名或标识码检索。一行一校，包含官网、档案路径、一个标识候选、屏幕主色的来源状态，以及学校/院系模板记录数。
2. 打开该校 `VISUAL.md` 查看全部校徽、校名文字、组合标识、调色板和VI入口。一个候选的具体构成、格式和读取状态会保留在索引中。
3. 在 [`indexes/ppt-resources.csv`](../indexes/ppt-resources.csv) 筛选该校。按 `category`、`official`、`use_scope`、`formats` 和 `edition_year` 选择模板与素材。
4. 需要实际模板文件时，读取 [`indexes/ppt-template-files.csv`](../indexes/ppt-template-files.csv)：每行一个已读取结构的PPTX或压缩包内PPTX，包含页数、画幅、声明字体、可编辑文本节点及内容哈希。
5. 需要引用校训、简介或人数时，再读 `PROFILE.md` 或 `profile.yaml`。统计数据须同时读取 `basis` 和 `source_as_of`，采集日期不是统计日期。

## 分类与层级

| 层级 | 分类 | 适用方式 |
| --- | --- | --- |
| 单校官方资料 | 校徽/校名/组合标识、标准色、印刷色、VI使用规范 | 标识文件和色彩分别按来源核对；不得把页眉组合图称为纯校徽 |
| 学校发布的模板 | `official_template`，`use_scope=school` | 使用学校通用模板；年份是发布标签明确写出的版本年 |
| 院系发布的模板 | `official_template`，`use_scope=department` | 仅用于对应学院/研究所场景；发布单位单独保留 |
| 官方视觉素材 | `official_visual_resource` | 可能是装在PPTX里的校徽或VI示例，不能直接当作整套演示模板 |
| 社区演示主题 | `community_template` | 区分PPTX、Marp和Beamer，按上游工具与材料说明使用 |
| 社区矢量源码 | `community_logo_source` | TikZ/TeX源码需要用户导出图形后使用；库内仅记录固定版本入口 |
| 社区校徽参考 | `community_logo_reference` | 上游校徽/组合图整理入口，文件状态须继续读单校视觉档案 |
| 社区校史参考 | `community_history_reference` | 用于介绍类PPT的校史检索，不能计为演示模板 |
| 社区目录提供的模板线索 | `community_template_reference` | 原目录指向学校资源，须打开目标页核对，不直接标成校方已核验模板 |

校庆专用资源在 `visual.vi_resources[].kinds` 标明“校庆专用”。它们不用于填通用标准色。学校通用模板、院系模板、社区主题和校庆素材各有独立记录。

## 配色怎么读

- `method=official_vi`：校方页面或手册公布的数字。公开了RGB才记录对应HEX；仅公布CMYK/Pantone时，HEX/RGB为空。`label`、`role` 和 `basis` 说明是校徽、校名文字、并列基调色还是主辅色。
- `manual_derived`、`badge_sample`、`community_logo_sample`：从标识文件取色的设计参考。它们可以帮助选配色，但不代表学校公布的VI标准。
- `community_theme`：社区主题作者使用的色值。
- `availability=conflict`：保留来源中互不一致的候选数字，不自动选择。详情见 [`indexes/color-conflicts.csv`](../indexes/color-conflicts.csv)。

素材索引的 `color_status=official_print_only` 表示已知校方标准主色只公开印刷色。这时索引留空屏幕主色，页眉取色仍在原档案中作为参考；不会用金色页眉的采样色替代校方公布的蓝色印刷标准。

不要使用固定公式把CMYK直接转换成“官方RGB”；印刷与屏幕还涉及设备和色彩配置。并列基调色也不等于校方指定的主辅层级。

## 标识候选怎么选

`ppt-starter.csv` 的标识候选由可复现规则排序：优先已读取内容，再优先校方发布、明确的图形类型、矢量与透明信息。该排序只方便检索，不能证明图形现行版本或使用许可。

- `access_status=content_inspected` 才读过文件内容；保留真实格式、尺寸、矢量/位图表示和哈希。
- `site_identity` 是具体构成未判定的官网标识。它可能包含校徽与校名文字。
- `download_kind=archive_member` 时，主URL是压缩包入口。须同时读 `archive_url`、`archive_member`、`archive_sha256`，不能把它当作PNG直链。
- 白色/反白标识适用于深色底。具体底色和禁用组合以校方VI说明为准。

VISUAL.md的文件表直接显示版式/文件名及官网/社区发布层级。`logo-assets.csv`同时提供`title/variant/dimensions_in_filename`，可筛选蓝黑、横竖、中文与中英组合；文件名尺寸仍不代替实测宽高。日期、页面哈希和文件哈希分别用于追溯采集及文件内容。

## 模板访问与来源

`content_read=true` 的HTML记录只表示读过该网页；附件 `indexed_not_fetched` 表示尚未读取文件。资源的`formats`保留发布标签，实际读取后的格式另见`file_format`。未知目标和动态端点可能实际返回PPTX，也可能返回网页或验证页，不能凭后缀判断。

`download_status=content_inspected`表示读取了公开PPTX或压缩包结构。`file_inspection_status=target_page_read`表示目标实际为发布网页。`downloaded_format_only`用于只识别了旧OLE/RAR/7Z文件头的情况，不含幻灯片统计。读取失败的原因及各次尝试见单校档案的`file_inspection`。

文件索引中的`aspect_ratio`来自原EMU尺寸的精确比例。`font_names`是文件声明的字体，不表示用户已安装；`editable_text_runs`是非空文本节点数量，不保证所有元素可编辑；为0时可能主要使用图片。`theme_colors`只表示该模板的内部主题色，不能认作学校VI。`macro_enabled`和外部链接数量仅记录结构，采集程序不运行或访问它们。压缩包模板须同时读取`url`和`archive_member`。

社区资源固定到Git提交，校方网页保存采集日期与内容哈希。仓库不再分发校徽、模板、字体或原始官网全文。代码许可、数据许可与字体/校徽图形权利分别记录。

## AI助手读取示例

```python
import csv

code = "4131010248"  # 上海交通大学，换成目标学校标识码
with open("indexes/ppt-starter.csv", encoding="utf-8-sig") as f:
    school = next(r for r in csv.DictReader(f) if r["school_code"] == code)

with open("indexes/ppt-resources.csv", encoding="utf-8-sig") as f:
    choices = [r for r in csv.DictReader(f) if r["school_code"] == code]

print(school["profile_path"], school["color_method"], school["color_status"])
for resource in choices:
    print(resource["category"], resource["use_scope"],
          resource["formats"], resource["url"])
```

批量读取全部字段使用 [`indexes/profiles.jsonl`](../indexes/profiles.jsonl)。需要筛选图形类型、透明信息与来源时，使用 `logo-assets.csv`；配色使用 `color-palettes.csv`。派生索引均由单校 `profile.yaml` 生成，不另建一份手工事实源。

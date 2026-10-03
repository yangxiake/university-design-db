# 数据结构 v4

当前1412份单校档案使用 `schema_version: 4`。唯一字段范围为[主字段清单](../data/ppt-core-fields.yaml)，可执行约束为[JSON Schema](../data/profile-schema-v4.json)。v2/v3规范仅保留给历史版本与兼容测试，当前生成和验收使用v4。

## 单校层级

| 分组 | 内容 |
| --- | --- |
| identity | 教育部身份、英文名、官网与检索简称/别名 |
| classification | 互斥主类别、可重叠标签及归类依据 |
| research | 自动采集状态、待采事项与检查记录 |
| visual | 主辅色、标识文件、色卡、VI入口及校园意象 |
| culture | 建校年、可选校训及稳定文化资料 |
| resources | 官方PPT入口、用途说明及社区模板资源 |
| overview | 由教育部身份生成的短简介 |

招生、就业、排名、人数、面积、联系方式与学科统计分组不属于v4。白名单投影删除这些数据；导入器拒绝向v4写入非核心字段。

## 事实封套

正向事实包含 `value`、`availability: found`、`source`、`verified` 与 `checked_at`。建校年另有历史起点 `basis`；颜色另有 `method` 及取值依据。网页/文件哈希、固定上游提交与修订号在取得时保留。

- `unresearched`：尚未取得可以写入的事实。
- `not_found`：已进行有记录的检索，范围内未找到；不表示学校永久没有该资料。
- `conflict`：保留候选与依据，等待来源解释。
- `found`：有来源记录。`verified: auto`是自动核对；只有实际人工签核才标为`human`。

社区资料与校方直接发布分别标记。取色、官网背景色和社区主题属于PPT设计参考，不能写成学校官方VI标准。仅公布CMYK/Pantone的色卡保留屏幕色空值，部分CMYK原文与RGB/HEX不一致也按实际记录。

## 标识与模板

标识逐文件保留URL、来源页、类型、格式、尺寸、透明情况、读取状态与SHA256；压缩包另保留容器/成员哈希和定位路径。`content_inspected`表示实际读取文件数据，不表示独立确认学校现行VI或图形授权。

模板入口区分学校通用、院系专用及社区资源。页数、画幅、字体声明等来自实际文件结构读取；未读文件不标为已检查。图形、字体与模板不随本库重新分发。

## 生成与校验

`profile.yaml`是唯一事实源。PROFILE/VISUAL/OFFICIAL/COMMUNITY、CSV/JSONL索引和viewer由七项生成器派生。PPT导出仍为v1，可读取历史v3与当前v4档案；[导出约束](../data/ppt-export-schema-v1.json)独立版本化。

运行 `python scripts/check.py` 检查结构、语义、身份、RGB/HEX关系、来源与日期、文件状态、生成一致性及仓库只读性。主字段全部补齐另由[覆盖报告](ppt-core-coverage-2026.md)计算，校验通过不等于资料全量完备。

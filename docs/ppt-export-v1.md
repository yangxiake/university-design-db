# PPT精简数据 v1

此导出由1412份`profile.yaml`生成。`export_version: 1`是导出结构版本；`profile_schema_version: 4`是原档案结构版本。导出用于取PPT材料，完整主字段仍见`indexes/profiles.jsonl`和原档案；高维护成本扩展数据已剔除。

## 文件与层级

| 文件 | 内容 |
| --- | --- |
| [`ppt-profiles.jsonl`](../indexes/ppt-profiles.jsonl) | UTF-8，每行一校，包含候选、理由和逐项来源 |
| [`ppt-profiles.csv`](../indexes/ppt-profiles.csv) | UTF-8 BOM，每行一校，便查列加五个完整JSON结构列 |
| [`ppt-profiles-coverage.json`](../indexes/ppt-profiles-coverage.json) | 从导出实际计算的数量与屏幕主色选择状态 |
| [`ppt-export-schema-v1.json`](../data/ppt-export-schema-v1.json) | 可执行的JSON Schema，Draft 2020-12 |

所有记录以`school_code`关联教育部本科范围表。`name_zh`是该名单中的名称，简称、英文名和有来源的别名在`identity`里保存各自状态；旧名用于查找同一档案，不能创建重复身份。

| 字段组 | 内容与规则 |
| --- | --- |
| 顶层身份 | 标识码、校名、地区、分类标签、教育部来源、`profile_path` |
| `identity` | 中英文名称、简称、别名及官网事实；带原来源、日期和调查状态 |
| `logos` | 全部逐文件候选、调查状态、推荐标识ID及理由；不推荐未读取或读取失败文件 |
| `colors` | 官方数字色、仅印刷色、设计参考色、来源冲突、主辅色原事实及屏幕选择依据 |
| `templates` | PPT/视觉文件入口、学校/院系/社区适用范围、实际读取PPTX及压缩包成员结构 |
| `content` | 短简介、校训、建校年；保留完整事实封套和历史起点 |

正向事实和资源保留`source`、`verified`、`checked_at`。适用时保留`source_as_of`、方法、用途说明、Git提交、许可与内容哈希。校方发布身份与独立图形授权分别记录。空值保持原调查状态，不推出“学校没有”。

## 选择规则

### 标识

在`access_status=content_inspected`的候选中，依次比较已记录的校方发布、明确图形类型、矢量、透明背景、非反白标签及尺寸；排序与旧PPT索引一致。并列时沿用原档案稳定顺序。推荐只便利选择，未判断现行版本或授权。

`site_identity`仍是构成待核验的官网页眉图；`badge`、`wordmark`、`combination`分别是纯校徽、校名文字、徽名组合。`variant`和文件名保留版式标签。含白色/反白标签时附`preview_background_hint`，依据是标签；这只是深色预览提示，未声称像素测量或校方VI规则。灰色标识不新增彩色参考值。

`download_kind=archive_member`时保留`archive_url`、`archive_member`、`archive_sha256`和成员`sha256`。主URL是压缩包入口，不能当作PNG直链。读取失败候选仍保留`access_status=inspection_failed`，不进入推荐。

### 配色

- `official_digital`：校方VI有HEX/RGB的色卡；角色与具体用途看`role/basis`，不把所有官方色都称为主色。
- `official_print_only`：只有CMYK/Pantone证据，屏幕值留空。
- `references`：图片取色、社区主题等建议色，方法和来源独立保留。
- `screen_status=official_vi`：使用原主色事实中的校方数字值。
- `screen_status=official_print_only`：原主色仅有印刷证据，`screen_primary=null`；采样值仍在原事实或参考列表中。
- `screen_status=design_reference`：原主色事实是取样等建议值，`screen_primary`保留其方法，不能认作官方色。
- `screen_status=conflict`：主色自动选择为空，来源候选完整保存。辅色冲突另列，不删除已明确的主色。
- 原主色尚未调查或未找到时保持该状态，即使有其他参考色卡也不自动指定一个主色。

### 模板

`resources`只导出模板或PPT视觉文件入口。社区校徽字体、TikZ源码和校史引用仍可在原档案及既有`ppt-resources.csv`检索。学校通用、院系专用、社区和适用范围未明确分别标记为`school/department/community/unspecified`；标识PPTX文件仍归视觉资源，不称作模板。

`inspected_presentations`中的页数、画幅、字体声明和文本节点来自实际PPTX结构读取。压缩包内文件保留成员路径与容器哈希；`format: PPTX`只表示文件结构。Beamer/Marp格式在资源列表标明，未编译上游代码。模板内部`theme_colors`不等同学校VI。

## 读取示例

只使用Python标准库即可查询；命令输出JSONL，未匹配时返回非零退出码：

```bash
python3 scripts/read_ppt_profile.py --school-code 4111010003
python3 scripts/read_ppt_profile.py --province 北京市 --has-inspected-logo
python3 scripts/read_ppt_profile.py --color-status official_vi
python3 scripts/read_ppt_profile.py --query 清华
```

Python读取单校及来源：

```python
import json
from pathlib import Path

with Path('indexes/ppt-profiles.jsonl').open(encoding='utf-8') as handle:
    records = (json.loads(line) for line in handle)
    school = next(record for record in records if record['school_code'] == '4111010003')
print(school['logos']['reason'])
print(school['colors']['screen_status'], school['colors']['screen_primary'])
print(school['content']['motto']['source'])
```

CSV中的`identity_json/logos_json/colors_json/templates_json/content_json`保留与JSONL相同的结构。部分学校的模板列表较长，读取时提高标准库的字段上限：

```python
import csv
import json

csv.field_size_limit(32 * 1024 * 1024)
with open('indexes/ppt-profiles.csv', encoding='utf-8-sig', newline='') as handle:
    row = next(row for row in csv.DictReader(handle) if row['school_code'] == '4111010003')
logos = json.loads(row['logos_json'])
```

CSV便查列只摘取值和状态；完整引用依据以结构列或JSONL为准。CSV和JSONL均从档案重新生成，既有索引字段继续兼容。

ZIP内标识保留`archive_member`原始成员字符串和`archive_member_display`可读路径；下载后按原始字符串查找，再核对容器与成员各自的SHA-256。可读路径可能恢复了中文编码，不能拿它替代程序查找路径。配色中的`cmyk_text`为原文局部/异常印刷记法，`cmyk`为空时不能默认补齐通道。官方PDF的`document_metadata`只说明PDF页数、字节数与哈希，不等同PPTX结构或AI可编辑性。

## 生成与验证

```bash
.venv/bin/python scripts/ingest/build_ppt_profiles.py
.venv/bin/python scripts/check.py
```

检查不联网采集，不重写事实、视图或索引。结构规范与跨字段语义校验共同运行，过期导出会明确失败。

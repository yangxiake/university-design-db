# 官网简介、校区与开源补采进度

本轮按教育部2026本科范围1412所采集。学校数、取得的字段数与资料时效分别统计；当前资料仍为自动采集版本。

## 当前档案覆盖

| 字段 | 学校数 |
| --- | ---: |
| 重新组织的短摘要 | 825 |
| 学生人数（看总数/本科等口径） | 650 |
| 教职工/专任教师（看口径） | 620 |
| 校园面积（公顷） | 407 |
| 学位授权点层次与数量 | 109 |
| 官网明确校区 | 236所，566条 |

## 数值口径

| 字段 | 原文标注统计时间 | 未标统计时间 | 近似/下界数 |
| --- | ---: | ---: | ---: |
| 学生人数（看总数/本科等口径） | 66 | 584 | 398 |
| 教职工/专任教师（看口径） | 62 | 558 | 268 |
| 校园面积（公顷） | 40 | 367 | 136 |

source_as_of=undated表示原文没有可归属到该数值的统计日期，checked_at仅为采集日期。不得把这些数值表述为2026年精确统计。approximate与original_notation保留“约/近/余/多/以上”等标注；专任教师不改称全部教职工，本科生不改称全体学生。面积换算按1公顷=15亩=10000平方米。

摘要根据教育部身份信息与官网结构化事实重新组织，不复制宣传段落。校区记录只收明确列示的名称；缺失的地址/坐标保持空值。解析器排除部门简介、其他学校报道、规划人数、新校区面积及留学生内部子群人数。

## 追加的开源资料

| 仓库 | 固定版本 | 匹配记录数 |
| --- | --- | ---: |
| [realJerryKing/university-insight](https://github.com/realJerryKing/university-insight) | `ea2eb0a4a83d` | 143 |
| [Hipo/university-domains-list](https://github.com/Hipo/university-domains-list) | `603e10f51b67` | 272 |

两库均保留MIT许可、固定commit、字段子集哈希和逐校匹配依据。科研经费、实验室、生源细分、性别比例、师资估算、就业行业/雇主等原字段进入可追溯社区快照；估算院士数、笼统就业率与未经校方确认的数据不进入官方统计。Hipo中的历史英文名和域名不覆盖现行官方名称。

### 开源校徽压缩包

xioajiumi/Chinese_Universities的固定版本logo.zip中，763个独立文件按2026完整校名匹配，41个历史/未匹配名称留在待调查列表，不凭近似名称绑定。
文件以元数据和压缩包内路径纳入档案，图像不再分发。download_kind=archive_member的URL不是PNG直链；按archive_member从archive_url下载的压缩包中读取文件，并分别核对archive_sha256与sha256。社区校徽取色仅为参考，不覆盖官方VI颜色。

另排除1个假图像文件：上游吕梁学院.png实际为HTML网页，未当作校徽纳入；该校已有另一官网标识文件读取成功。

## 访问与缺项

记录1929次页面读取/失败尝试。

- `no_confirmed_homepage`：241所。
- `overview_access_or_identity_gap`：287所。
- `researched_partial`：884所。

失败页会尝试已发现的不同简介URL、首页重新发现的导航入口或另一协议。robots限制与跨校跳转停止；状态只描述本次访问，不认定永久无法获取。阳光高考公开目录本轮返回HTTP 412，未绕过限制；未将搜索摘要直接当作批量统计依据。

本轮同时评估blyenso-del/gaokao-score、ZsTs119/china-university-database、dataxiv/data-universities及woojoo520/china-university-logos：未取得明确数据再分发许可或对核心视觉/简介缺项无显著新增覆盖，未镜像这些仓库的数据。

逐校事实见universities/*/*/profile.yaml；批量用indexes/extended-facts.csv、indexes/campuses.csv、indexes/logo-assets.csv和indexes/profiles.jsonl。完整检索及版本台账见data/review/official-overviews-2026.jsonl、logo-archive-2026.json与supplemental-repositories-2026.json。

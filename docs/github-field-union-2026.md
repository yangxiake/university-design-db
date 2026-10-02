# GitHub字段并集与视觉资料覆盖

本报告比较本轮实际读取的仓库，不声称穷尽GitHub或已经达到全网最多字段。字段扩展与数据填充分别验收；未找到有来源数值的字段保持未采集。

## 仓库覆盖比较

| 仓库 | 原记录数 | 本科完整身份匹配数 | 字段组数 |
| --- | ---: | ---: | ---: |
| [xioajiumi/Chinese_Universities](https://github.com/xioajiumi/Chinese_Universities) | 582 | 556 | 10 |
| [damitheswitch/china-universities-dataset](https://github.com/damitheswitch/china-universities-dataset) | 582 | 569 | 13 |
| [Magicdover/China-Universities-2026](https://github.com/Magicdover/China-Universities-2026) | 188 | 184 | 21 |
| [HeyHuazi/SVGLOGO](https://github.com/HeyHuazi/SVGLOGO) | 120 | 115 | 4 |
| [CakeAL/beijing-univs-vis](https://github.com/CakeAL/beijing-univs-vis) | 87 | 45 | 6 |
| [RoboMaster/university_logos](https://github.com/RoboMaster/university_logos) | 184 | 85 | 4 |
| [realJerryKing/university-insight](https://github.com/realJerryKing/university-insight) | 148 | 143 | 10 |
| [Hipo/university-domains-list](https://github.com/Hipo/university-domains-list) | 399 | 272 | 6 |

基础数据两库各582条，高校全景库188条且字段较细；地区VI目录和校徽资源库补充下载格式、校名文字、资源访问条件与逐文件内容元数据。范围始终以教育部2026本科名单1412所为准。

## 上游字段逐项落点

### xioajiumi/Chinese_Universities

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `link` | 官网候选与社区快照 |
| `location` | identity.province，教育部值优先；快照保留原值 |
| `logo` | visual.logo_assets[].url |
| `name` | identity.name_zh，教育部值优先 |
| `name_eng` | identity.name_en |
| `note` | community.snapshots历史标签原值 |
| `rank` | rankings.entries[].rank (2021) |
| `school_level` | rankings.entries[].indicators.school_level |
| `total_score` | rankings.entries[].score |
| `type` | institution.school_type |

### damitheswitch/china-universities-dataset

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `category` | institution.school_type |
| `city` | identity.city，教育部值优先；英文原值保留快照 |
| `country` | institution.country |
| `languages_of_instruction` | institution.languages_of_instruction |
| `logo_url` | 排除已发现的图库照片；原记录保留快照 |
| `name` | identity.name_en |
| `name_zh` | identity.name_zh，教育部值优先 |
| `province` | identity.province，教育部值优先；英文原值保留快照 |
| `shanghairanking` | rankings.entries（publisher/year/scope/rank/score/indicators/upstream_url），tags为institution.groups |
| `slug` | identity.external_identifiers |
| `slug_aliases` | identity.slug_aliases |
| `uni_type` | institution.nature |
| `website` | 官网候选 / resources.english_website |

### Magicdover/China-Universities-2026

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `a` | academics.subject_assessments[].grade=A |
| `abbr` | identity.short_name_zh |
| `admin` | identity.authority，教育部值优先 |
| `aminus` | academics.subject_assessments[].grade=A- |
| `aplus` | academics.subject_assessments[].grade=A+ |
| `city` | identity.city，教育部值优先 |
| `emp` | community.snapshots（评论不替代就业率） |
| `en` | identity.name_en |
| `enAbbr` | identity.short_name_en |
| `firstClass` | academics.double_first_class_disciplines；概括/占位文字仅保留快照 |
| `founded` | culture.founded_year，保留社区历史口径 |
| `id` | community.snapshots原始标识 |
| `intro` | community.snapshots（原始简介，不作为客观事实摘要） |
| `lat` | location.coordinates.latitude |
| `lng` | location.coordinates.longitude |
| `name` | identity.name_zh，教育部值优先 |
| `province` | identity.province，教育部值优先 |
| `score` | admissions.cutoffs（year/region/curriculum/batch/minimum_score/minimum_rank） |
| `tags` | institution.groups / community.snapshots |
| `tier` | community.snapshots（主观梯队不作客观学校类别） |
| `type` | institution.school_type |

### HeyHuazi/SVGLOGO

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `file` | visual.logo_assets（badge） |
| `title` | 教育部完整校名匹配 |
| `url` | community.snapshots原始网站线索，未直接覆盖官网 |
| `wordmark` | visual.logo_assets（wordmark） |

### CakeAL/beijing-univs-vis

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `school_name` | identity.short_name_en及学校全称匹配 |
| `campus_district` | visual.vi_resources[].campus_district |
| `vi_urls` | visual.vi_resources[].url |
| `kinds` | visual.vi_resources[].kinds |
| `formats` | visual.vi_resources[].formats |
| `access_requirement` | visual.vi_resources[].access_requirement |

### RoboMaster/university_logos

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `english_directory` | 唯一英文全名匹配 |
| `logo_file` | visual.logo_assets[].url/upstream_path |
| `color_variant` | visual.logo_assets[].variant（原文件标记，不自动生成HEX） |
| `dimensions_in_filename` | visual.logo_assets[].dimensions_in_filename（仅提示；尺寸以内容检查为准） |

### realJerryKing/university-insight

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `aliases` | identity.aliases社区检索别名，非正式简称 |
| `一流学科` | community.snapshots，概括/占位文字不当学科名单 |
| `城市` | 身份表优先；社区快照保留原值 |
| `就业概况` | community.snapshots，保留就业率/深造率/行业/雇主/年份，不作官方统计 |
| `层次` | community.snapshots历史标签 |
| `师资概况` | community.snapshots，完整保留估算/兼职/双聘/来源与核实说明 |
| `生源概况` | community.snapshots，保留规模/本科硕士博士/性别比/年份，约数不改为精确统计 |
| `科研概况` | community.snapshots，保留经费/实验室/平台/年份，未逐项校方确认 |
| `类型` | community.snapshots院校类型原值 |
| `网址` | community.snapshots网址线索，不覆盖已确认官网 |

### Hipo/university-domains-list

| 上游字段 | 本库落点/处理 |
| --- | --- |
| `alpha_two_code` | community.snapshots国家两字母代码 |
| `country` | community.snapshots国家原值 |
| `domains` | community.snapshots域名数组，完整主机名唯一匹配 |
| `name` | community.snapshots历史英文名称，不覆盖现行英文名 |
| `state-province` | community.snapshots省级名称/空值 |
| `web_pages` | community.snapshots网址数组 |

## v3覆盖情况

| 项目 | 学校数 | 记录数 |
| --- | ---: | ---: |
| 逐文件校徽/校名资源 | 1214 | 3374 |
| 其中官网发布标识文件 | 1015 | 1394 |
| 结构化配色 | 1068 | 4879 |
| 其中校方公布色值 | 61 | 104 |
| 其中仅公布印刷色的条目 | 14 | 32 |
| 标识介绍、VI规范与下载线索 | 520 | 1510 |
| 历史排名 | 569 | 1117 |
| 学科评估节选 | 136 | 764 |
| 重庆2025录取参考 | 166 | 277 |
| 上游字段快照 | 670 | 1838 |
| 官网明确列示校区 | 236 | 566 |

### 校徽文件检查

| 状态 | 文件数 |
| --- | ---: |
| content_inspected | 2719 |
| indexed_not_fetched | 599 |
| inspection_failed | 56 |

只有content_inspected读取了文件内容；历史外部CDN地址仅索引，不等于当前可下载。学校现行版本与图形授权未作人工签核。site_identity有1388条，是具体构成待核验的官网页眉标识，不能计为已确认纯校徽。

其中763条为压缩包内文件：download_kind=archive_member，须读取archive_url、archive_member与archive_sha256；主URL不是PNG直链，文件内容哈希和压缩包哈希分别保存。

### 配色方法

| 方法 | 颜色记录数 |
| --- | ---: |
| badge_sample | 1 |
| community_logo_sample | 3103 |
| community_theme | 10 |
| manual_derived | 1661 |
| official_vi | 104 |

颜色数包含多源同色、主/辅色和建议色，不等于有官方标准色的学校数量。社区主题与校徽取色不覆盖主色官方结论。

### 新增事实字段

| 字段 | 有来源值的学校数 |
| --- | ---: |
| `identity.short_name_zh` | 184 |
| `identity.short_name_en` | 204 |
| `identity.aliases` | 72 |
| `identity.slug_aliases` | 561 |
| `institution.school_type` | 627 |
| `institution.nature` | 435 |
| `institution.country` | 561 |
| `institution.languages_of_instruction` | 12 |
| `institution.groups` | 149 |
| `location.address` | 709 |
| `location.postal_code` | 523 |
| `location.coordinates` | 184 |
| `overview.summary_zh` | 825 |
| `overview.summary_en` | 0 |
| `statistics.student_count` | 650 |
| `statistics.faculty_count` | 620 |
| `statistics.campus_area_hectares` | 407 |
| `academics.double_first_class_disciplines` | 140 |
| `academics.degree_authorizations` | 109 |
| `employment.summary` | 0 |
| `employment.report_url` | 0 |
| `resources.admissions_url` | 829 |
| `resources.career_url` | 488 |
| `resources.english_website` | 451 |
| `resources.information_disclosure_url` | 817 |
| `contacts.phone` | 386 |
| `contacts.email` | 241 |

## 扩展字段的完整性与口径

新增27个事实字段与12个结构化集合。地址、校区、邮编、办公联系方式、学生/教职工人数、面积、学位授权、专业录取、招生计划与就业指标已有明确字段，当前无可可靠导入的数据时为空；不从现有字段推断这些数值。

学科来源内部出现同一学科多个等级时，availability=conflict、grade=null并保留candidates；当前1条，不自动选择。

学生/教职工人数、面积保留统计日期和basis；未标注日期明确为source_as_of=undated，不能把checked_at当作统计日期。近似/下界数保留original_notation和approximate，专任教师/本科生与全校总量的口径分别标明。录取与计划须带年份、地区、科类、批次和招生类型；排名须带发布方、榜单、年份和范围。校徽保留文件地址、真实格式、宽高、纯矢量判断、透明信息、哈希、独立图形许可与仓库许可。

原始简介、就业评论、主观tier，以及已发现的占位学科文本完整保存在MIT社区快照中；未当作学校官方事实。发现的Pexels照片不加入校徽集合。

字段定义见[data/profile-schema-v3.yaml](../data/profile-schema-v3.yaml)，导入台账见[data/review/github-field-union-2026.json](../data/review/github-field-union-2026.json)。

AI批量读取用indexes/profiles.jsonl；逐项筛选用logo-assets.csv、color-palettes.csv、extended-facts.csv、rankings.csv、subject-assessments.csv和admission-cutoffs.csv。

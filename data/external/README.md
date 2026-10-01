# 第三方资料与来源层级

本目录收匹配数据子集、版本记录和独立许可。单校当前资料以profile.yaml为准；完整上游仓库与读取图形仅用于本地检查，不纳入本库再分发。

| 来源 | 使用方式 | 仓库许可 | 匹配学校 |
| --- | --- | --- | ---: |
| [xioajiumi/Chinese_Universities](https://github.com/xioajiumi/Chinese_Universities) | v3字段并集/逐文件资料 | MIT | 556 |
| [damitheswitch/china-universities-dataset](https://github.com/damitheswitch/china-universities-dataset) | v3字段并集/逐文件资料 | MIT | 569 |
| [Magicdover/China-Universities-2026](https://github.com/Magicdover/China-Universities-2026) | v3字段并集/逐文件资料 | MIT | 184 |
| [HeyHuazi/SVGLOGO](https://github.com/HeyHuazi/SVGLOGO) | v3字段并集/逐文件资料 | MIT | 115 |
| [CakeAL/beijing-univs-vis](https://github.com/CakeAL/beijing-univs-vis) | v3字段并集/逐文件资料 | not_declared | 45 |
| [RoboMaster/university_logos](https://github.com/RoboMaster/university_logos) | v3字段并集/逐文件资料 | not_declared | 85 |
| [tuna/THU-Beamer-Theme](https://github.com/tuna/THU-Beamer-Theme) | 社区资源入口 | LPPL-1.3c | 1 |
| [CouesF/marp-theme-zju](https://github.com/CouesF/marp-theme-zju) | 社区资源入口 | not_declared | 1 |
| [weijianwen/SJTU-logo-banner](https://github.com/weijianwen/SJTU-logo-banner) | 社区资源入口 | not_declared | 1 |
| [sjtug/SJTUBeamer](https://github.com/sjtug/SJTUBeamer) | 社区资源入口 | Apache-2.0 | 1 |
| [ustctug/ustcbeamer](https://github.com/ustctug/ustcbeamer) | 社区资源入口 | LPPL-1.3c | 1 |
| [TouchFishPioneer/SEU-Beamer-Slide](https://github.com/TouchFishPioneer/SEU-Beamer-Slide) | 社区资源入口 | GPL-3.0 | 1 |
| [icgw/ucas-beamer](https://github.com/icgw/ucas-beamer) | 社区资源入口 | MIT | 1 |
| [FvNCCR228/SCU-Beamer-Theme](https://github.com/FvNCCR228/SCU-Beamer-Theme) | 社区资源入口 | LPPL-1.3c | 1 |
| [inFaaa/PKU-Beamer-Theme](https://github.com/inFaaa/PKU-Beamer-Theme) | 社区资源入口 | not_declared | 1 |
| [liu-qilong/college-beamer](https://github.com/liu-qilong/college-beamer) | 社区资源入口 | CC-BY-4.0 | 22 |
| [FitchCode/AllShoolData](https://github.com/FitchCode/AllShoolData) | 仅网址线索 | not_declared | 0 |
| [PotoYang/UniversityCareerWebPage](https://github.com/PotoYang/UniversityCareerWebPage) | MIT匹配子集 | MIT | 0 |
| [lovefc/china_school_badge](https://github.com/lovefc/china_school_badge) | 社区资源入口 | Apache-2.0 | 294 |
| [jtchen2k/hcu](https://github.com/jtchen2k/hcu) | 社区资源入口 | GPL-3.0 | 137 |
| [DiamonWoo/Laosheng.top](https://github.com/DiamonWoo/Laosheng.top) | 仅网址线索 | CC-BY-NC-ND-3.0 | 0 |
| [realJerryKing/university-insight](https://github.com/realJerryKing/university-insight) | MIT匹配快照 | MIT | 143 |
| [Hipo/university-domains-list](https://github.com/Hipo/university-domains-list) | MIT匹配快照 | MIT | 271 |

字段并集模式的匹配数是数据/文件/VI目录匹配学校数；资源入口模式是该仓库关联学校数。同校可由多个仓库提供资料，不能相加当作唯一学校覆盖。

## 导入规则

- xioajiumi的582校2021数据：英文名、学校类型、2021排名/指标、校徽具体链接及完整字段匹配快照。
- 同仓库logo.zip另有763个图像文件按2026完整校名匹配，存压缩包内文件路径、真实图像格式、尺寸、哈希及参考取色；吕梁学院.png实际为HTML网页，已排除。图像不再分发，历史校名不自动绑定现行学校。
- damitheswitch的582校2026数据：英文名、类型/性质、国家/语言、检索标识、2026排名/指标与完整快照。其logo_url实际为Pexels照片，本库排除；不能将其README的“校徽”说明当作已验证事实。
- Magicdover的188校全景数据：简称、近似坐标、学科与招生历史参考、校徽链接。主观梯队、宣传简介、就业评论仅保留MIT快照。
- HeyHuazi读取学校YAML元数据并识别具体校徽/校名文件。RoboMaster按唯一完整英文名匹配后收具体文件链接；两者图形不镜像。
- CakeAL的北京VI目录只保存有来源的资源链接、格式和校园认证条件，不复制完整无许可目录。
- 就业目录保留MIT匹配子集，就业门户作为带历史版本的社区链接，不推出当前校园主页。
- FitchCode没有许可；Laosheng.top采用CC-BY-NC-ND等站点条款，仅作官网网址线索，不镜像原数据。
- lovefc校徽字体LICENSE为Apache-2.0，README另有保留作者与禁止倒卖说明，字体不镜像。jtchen2k校史项目只提供版本与参考入口，不导入占位描述。
- hewguo/gaokao2025只参考README的数据字段结构，没有获得现成数据子集；未执行爬虫或复制代码。无许可Gist中学生/教职工/面积/双语简介字段仅参考结构，不导入内容。
- realJerryKing原字段保留资料年份、约数、师资统计中双聘/兼职说明与核实状态；科研、生源、师资与就业估算资料在MIT快照中查询，不成为校方现行统计。
- Hipo以完整官网主机名或现有英文全名唯一匹配，保留国家代码、历史英文名称、省级名称、域名与网址数组；不以母校域名包含关系绑定独立学院，不覆盖现行官方英文名称。

每个再分发的MIT子集保留LICENSE及SOURCE.yaml/FIELDS-SOURCE.yaml。profiles.jsonl与其他派生视图不改变社区数据原许可。仓库代码/数据许可不是校徽图形或学校商标的许可。逐字段落点及有效覆盖见[字段并集报告](../../docs/github-field-union-2026.md)。

## 追加采集的图形时间说明

压缩包内763个图像只收链接、成员路径与文件元数据；图形版本日期为unspecified。2021排名年份和ZIP内部文件时间均不能当作学校标识设计年份。

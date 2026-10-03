# 第三方资料与来源层级

本目录收匹配数据子集、版本记录和独立许可。单校当前资料以profile.yaml为准；完整上游仓库与读取图形仅用于本地检查，不纳入本库再分发。

| 来源 | 使用方式 | 仓库许可 | 匹配学校 |
| --- | --- | --- | ---: |
| [xioajiumi/Chinese_Universities](https://github.com/xioajiumi/Chinese_Universities) | PPT主字段/逐文件资料 | MIT | 556 |
| [damitheswitch/china-universities-dataset](https://github.com/damitheswitch/china-universities-dataset) | PPT主字段/逐文件资料 | MIT | 569 |
| [Magicdover/China-Universities-2026](https://github.com/Magicdover/China-Universities-2026) | PPT主字段/逐文件资料 | MIT | 184 |
| [HeyHuazi/SVGLOGO](https://github.com/HeyHuazi/SVGLOGO) | PPT主字段/逐文件资料 | MIT | 115 |
| [CakeAL/beijing-univs-vis](https://github.com/CakeAL/beijing-univs-vis) | PPT主字段/逐文件资料 | not_declared | 45 |
| [RoboMaster/university_logos](https://github.com/RoboMaster/university_logos) | PPT主字段/逐文件资料 | not_declared | 85 |
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
| [lovefc/china_school_badge](https://github.com/lovefc/china_school_badge) | 社区资源入口 | Apache-2.0 | 294 |
| [jtchen2k/hcu](https://github.com/jtchen2k/hcu) | 社区资源入口 | GPL-3.0 | 137 |
| [DiamonWoo/Laosheng.top](https://github.com/DiamonWoo/Laosheng.top) | 仅网址线索 | CC-BY-NC-ND-3.0 | 0 |
| [realJerryKing/university-insight](https://github.com/realJerryKing/university-insight) | PPT主字段子集 | MIT | 143 |
| [Hipo/university-domains-list](https://github.com/Hipo/university-domains-list) | PPT主字段子集 | MIT | 271 |
| [wanzhenchn/Visual_Identity_System_Chinese_University](https://github.com/wanzhenchn/Visual_Identity_System_Chinese_University) | 官方VI入口线索，实际回源核对 | not_declared | 97 |

主字段模式的匹配数是数据/文件/VI目录匹配学校数；资源入口模式是该仓库关联学校数。同校可由多个仓库提供资料，不能相加当作唯一学校覆盖。

## 当前字段裁剪

2026-10-02按PPT用途裁剪已纳入的许可数据子集。原仓库、commit、许可不变；`FIELDS-SOURCE.yaml` 记录裁剪后的字段和子集SHA256。

- xioajiumi：校名、英文名、所在地、官网候选与校徽链接；logo.zip保留包内路径、真实格式、尺寸、哈希和参考色，不再分发图像。
- damitheswitch：校名、英文名、地区和官网候选。其Pexels照片未作为校徽；排名、语言、类型及坐标扩展已删除。
- Magicdover：校名、简称、英文名、建校年、地区与主管部门；招生、就业、学科、坐标、主观梯队和宣传段落删除。
- realJerryKing与Hipo：只留官网候选/身份匹配字段；动态师资、生源、科研及就业描述删除。
- HeyHuazi、RoboMaster、北京VI目录和其他视觉仓库：只读取逐文件标识、VI、色值线索与演示主题，保留访问条件和独立许可。
- wanzhenchn目录固定到 `a1c76a6061941ff2c37287a7b9021508afba0e4b`，仅提供97所学校VI入口线索；学校原页面/附件实际读取后才能采用。目录不是色值或授权证明。

素材按现行完整校名及学校标识码匹配。历史名称、验证页、通用照片及名称不符的图形不采用。图形本体不再分发；仓库代码许可不替代学校图形授权。无许可资源只保留出处与入口。

字段范围见[ppt-core-fields.yaml](../ppt-core-fields.yaml)，实际学校资料以v4 `profile.yaml`为准。

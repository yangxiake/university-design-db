# 第三方资料与来源层级

本目录收匹配数据子集、版本记录和许可。单校当前事实以profile.yaml为准，下载检查过的完整上游源文件只存在忽略的tmp中。

| 来源 | 使用方式 | 许可 | 资源匹配学校 |
| --- | --- | --- | ---: |
| [xioajiumi/Chinese_Universities](https://github.com/xioajiumi/Chinese_Universities) | MIT匹配子集 | MIT | 0 |
| [damitheswitch/china-universities-dataset](https://github.com/damitheswitch/china-universities-dataset) | MIT匹配子集 | MIT | 0 |
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

## 采用及排除规则

- 两份582校数据集按完整中文校名匹配，仅补英文名与网址候选。匹配子集附原MIT许可和SOURCE.yaml。2021版与声称2026版不能当作两份独立的校方证据。
- 就业目录保留MIT匹配子集，推导首页只作候选，访问后再核对。
- FitchCode目录未声明许可；Laosheng.top使用CC-BY-NC-ND等站点条款。仅读取用于定位的网址事实及出处，不镜像其文章或完整目录，不将其内容重许可为CC BY。
- 其余主题、校徽及校史项目只记录入口、适用学校、提交和许可；不镜像校徽、字体、主题代码或校史正文。
- damitheswitch数据的部分logo_url指向Pexels图库照片，未作为校徽导入。hcu的英文缩写、占位描述和年份未直接导入校方事实。
- lovefc校徽索引LICENSE为Apache-2.0，页面另有保留作者及禁止倒卖说明，记录条款差异；不分发其字体。
- 未声明许可的资源仅链接。学校标识及模板的使用仍看学校与上游权利人的规则。

锁定的上游提交及导入参数见[repositories.yaml](repositories.yaml)；检查和排除记录见[来源评估表](../review/public-repository-assessment-2026.csv)。

本轮不需要人工签核，所有采集结果标为auto，不将社区项目改称校方发布。

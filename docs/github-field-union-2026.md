# 开源来源与PPT核心映射

2026-10-02按用户决定裁剪字段；本报告只比较实际保留的主字段子集。固定上游版本、匹配身份和许可继续可复核。

| 仓库 | 匹配学校 | 当前保留上游字段 |
| --- | ---: | --- |
| [HeyHuazi/SVGLOGO](https://github.com/HeyHuazi/SVGLOGO/tree/142498f527ac2dd3116cc1feccb9670879839f74) | 115 | file、title、url、wordmark |
| [Hipo/university-domains-list](https://github.com/Hipo/university-domains-list/tree/603e10f51b67c6553b9bca9aecc0db4c2417ed10) | 272 | domains、name、web_pages |
| [Magicdover/China-Universities-2026](https://github.com/Magicdover/China-Universities-2026/tree/419bdc7ce6956fc88c2b70b3979f170b6666f111) | 184 | abbr、admin、city、en、enAbbr、founded、name、province |
| [damitheswitch/china-universities-dataset](https://github.com/damitheswitch/china-universities-dataset/tree/5eaa2a93f86ac322d53a36da9977d9a4c80f1f56) | 569 | city、name、name_zh、province、website |
| [realJerryKing/university-insight](https://github.com/realJerryKing/university-insight/tree/ea2eb0a4a83deb83075675f6e319ed30685b33d5) | 143 | 网址 |
| [xioajiumi/Chinese_Universities](https://github.com/xioajiumi/Chinese_Universities/tree/e088fddc329a6f0148ca72fd3b4d0fe069f13e3a) | 556 | link、location、logo、name、name_eng |

名称、简称与英文名映射到identity；建校年映射到culture并保留来源口径；网址作为官网候选；具体标识与色卡映射到visual。模板仓库和无许可VI目录保存入口与元数据，详见[来源层级](../data/external/README.md)。

招生、就业、排名、学科统计、人数、面积与联系方式已从档案、索引和许可子集删除，不参与后续采集及验收。不是按字段数量评估本库。

| 素材 | 有记录学校 | 条目 |
| --- | ---: | ---: |
| 标识 | 1374 | 3790 |
| 配色（含建议色） | 1364 | 5802 |
| 校方色值 | 124 | 449 |

逐校必备缺口见[主字段覆盖](ppt-core-coverage-2026.md)；机器读取用 `indexes/ppt-profiles.jsonl`。`indexes/core-facts.csv`、`logo-assets.csv` 和 `color-palettes.csv` 支持按字段筛选。

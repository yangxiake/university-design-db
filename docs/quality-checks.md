# 统一质量检查

## 本地入口

Python 3.9+和Node.js 24，Python依赖安装到本地虚拟环境，网页规则测试不需要npm依赖：

```bash
.venv/bin/pip install -r requirements-quality.txt
.venv/bin/python scripts/check.py
```

默认并行2项独立检查，可用`--jobs 1`顺序执行；最多4项。Node不在PATH中时传`--node /实际路径/node`，或设置`NODE_BINARY`。检查已有资料，不下载学校网页或文件，不生成或修补档案、索引及人工选择。检查前后对全部已跟踪和未忽略的仓库文件计算哈希，修改文件会失败。运行期间请勿编辑这些文件。

| 检查 | 内容 |
| --- | --- |
| 档案语义 | 1412个唯一身份及范围对应、事实来源、非未来日期、统计口径、RGB/HEX一致、官方标记、文件读取与结构关系 |
| JSON Schema | v3单校档案及v1 PPT导出结构、数据类型、状态条件、来源日期、印刷色与屏幕空值规则 |
| Python测试 | 原有110项与4项目录数据测试，共114项 |
| 网页规则测试 | 12项：同记录条件匹配、搜索、来源、透明状态、预览背景、ZIP成员、危险URL及实际空屏幕色 |
| 七项生成一致性 | OFFICIAL、COMMUNITY、PROFILE/VISUAL和完整索引、分类索引、既有PPT索引、PPT导出、viewer地区数据 |
| 仓库检查 | `git diff --check`及检查前后文件哈希一致 |

字段错误显示学校标识码和字段路径，过期视图显示文件路径；重新生成需单独执行对应脚本。生成器使用LibYAML的安全解析器，缺少该解析器时退回Python安全解析器，拒绝Python对象标签。生成一致性检查确保现有派生内容兼容。

## GitHub Actions

工作流为[Data quality](https://github.com/yangxiake/university-design-db/actions/workflows/quality.yml)。推送、PR及手动触发运行，Python矩阵为3.9、3.13，两套均使用Node.js 24；安装依赖后执行同一本地检查入口。标准校验不调用联网采集脚本。工作流只获仓库读取权限，官方checkout/setup-python/setup-node操作固定到完整提交SHA。

jsonschema固定为4.25.1，以兼容Python 3.9最低版本，版本依据见[PyPI元数据](https://pypi.org/project/jsonschema/4.25.1/)。每套运行单独显示结果，超时或任何检查失败都不计为通过。

## M1/M2验收（2026-10-02）

- 全部1412份档案和1412条精简导出通过结构与语义检查。
- 新增边界覆盖身份重复、无来源正向事实、RGB/HEX不一致、过期导出、仅印刷主色、来源冲突、访问失败、反白/灰色标识、压缩包成员、CSV完整结构、统计口径、社区标记及查询结果。
- 本地Python 3.9完整检查通过：110项测试、11项质量关卡；仓库文件哈希保持一致。
- GitHub Python 3.9、3.13两套完整检查均通过，每套运行110项测试及11项质量关卡。验收运行：[Data quality #36970623141](https://github.com/yangxiake/university-design-db/actions/runs/36970623141)，对应提交`1a6c8aaec439a409d785f36386d39fcd15729e1e`。

## M3本地验收（2026-10-02）

- Python 3.9完整检查通过114项测试，Node.js 24.19.0通过12项网页规则测试，共13项质量检查通过；仓库前后文件哈希一致。
- 1412所身份、31个地区分包及原PPT导出哈希完整对应，地区记录与原导出逐条相等。
- 实际浏览器验收与兼容性限制见[素材目录说明](viewer-guide.md)。网页预览失败不会写回文件读取状态。
- GitHub使用同一入口，每套Python矩阵均运行网页规则及生成一致性检查；最新远程运行结果见[Data quality工作流](https://github.com/yangxiake/university-design-db/actions/workflows/quality.yml)。

## PPT导出实际数量

| 项目 | 数量 |
| --- | ---: |
| 学校身份 | 1412 |
| 标识候选 | 3374 |
| 有已读取标识候选的学校 | 1196 |
| PPT模板/视觉资源入口 | 174 |
| 已读取PPTX记录，含压缩包成员 | 57 |
| 官方屏幕主色选择 | 43 |
| 仅官方印刷主色，屏幕为空 | 11 |
| 设计参考主色选择 | 341 |
| 主色来源冲突，暂停选择 | 5 |
| 主色已检索未找到 | 5 |
| 原主色尚未调查，未自动选择 | 1007 |

数量直接来自[`ppt-profiles-coverage.json`](../indexes/ppt-profiles-coverage.json)。屏幕主色选择状态按原主色事实统计；未选择主色的学校仍可能有已记录的配色或参考色卡。导出集中提供PPT入口，社区校徽/源码/校史引用不计入174条入口；这些仍在既有669条综合PPT资源引用中保留。

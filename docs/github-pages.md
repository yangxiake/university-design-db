# 在线素材目录

在线入口：[高校 PPT 素材目录](https://yangxiake.github.io/university-design-db/)。浏览器直接搜索学校、筛选素材、查看配色与模板入口，并复制或下载单校 JSON 给 AI。地址参数保存学校和筛选，分享单校地址时会保留这些条件。

本项目使用公开仓库的 GitHub Pages 和标准 GitHub 托管运行器，使用 GitHub 提供的免费域名。无需购买服务器或自定义域名，说明见[创建 Pages 站点](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)。

## 技术栈与构建产物

网页为原生 HTML、CSS 和 JavaScript 模块，数据为已生成的 JSON。仓库没有 `package.json`、npm/pnpm/yarn lock 文件或 Vite、React、Vue、Astro、Next.js 配置。Node.js 24 用于网页规则测试，构建仅需 Python 标准库。

正式构建命令：

```bash
python scripts/build_pages.py --output-dir tmp/github-pages
```

构建脚本将网页放到产物根目录，按固定列表发布 6 个页面/样式/脚本文件、检索目录与 31 个地区 JSON，另附 `.nojekyll` 和 `deployment.json`。当前共 40 个文件，约 17.7 MB。清单记录源提交、学校/地区数量、导出哈希及每个站点文件的哈希。上传的是 `tmp/github-pages/`，不会上传整个源码仓库。

产物不包含本机图片缓存、原始校徽/模板/字体、研究日志、开发环境或测试文件。图形仍从记录的原来源载入，ZIP/PDF 资源通过原入口获取；原站网络或浏览器限制仍可能导致图形预览失败。完整档案和页脚说明链接指向本次部署提交的 GitHub 文件；本地网页继续使用原相对路径。

页面、样式、脚本导入及 JSON 请求使用相对路径，适配现有 `/university-design-db/` 项目地址。学校、筛选状态放在查询参数中，详情导航使用 hash，不依赖服务器提供 SPA 路由重写。现有页面没有独立 favicon、字体包或图片目录，图形使用原来源链接。当前 Pages 没有自定义域名，main 与旧发布分支均无 `CNAME`。

## 自动检查、构建和部署

源代码和资料由 main 维护，工作流为 `.github/workflows/deploy-pages.yml`。每次推送 main 或在 Actions 页面手动运行时：

1. 复用 `.github/workflows/quality.yml` 的 Python 3.9、3.13 检查，安装 `requirements-quality.txt` 和 Node.js 24，执行 `python scripts/check.py`。
2. 两套检查全部成功后，通过官方 `configure-pages` 读取 Pages 配置，再运行上述静态构建命令。
3. 官方 `upload-pages-artifact` 上传构建目录，包含用于保持产物清单一致的 `.nojekyll`。
4. 官方 `deploy-pages` 在 `github-pages` environment 部署 artifact。

手动运行仅允许 main 进入发布流程。检查、构建失败时不会部署；部署共用 `github-pages` concurrency，正在进行的部署不会被新提交中途取消。官方 Actions 固定到完整提交 SHA。

质量检查只有 `contents: read`；构建另有读取 Pages 配置的 `pages: read`；部署具有 `contents: read`、`pages: write`、`id-token: write`。流程不推送源码或发布分支，不需要个人访问令牌或额外仓库 secrets。

Pages 设置使用 `GitHub Actions`。修改入口：[仓库 Settings → Pages](https://github.com/yangxiake/university-design-db/settings/pages) → Build and deployment → Source → GitHub Actions。官方机制见[自定义 Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

旧 `codex/gh-pages` 分支保留已有发布内容，迁移后不再用于正常更新。`scripts/publish_pages.py` 是旧分支发布工具，自动部署不调用它。不要因 Actions 暂时失败自行切回分支发布，应先检查失败任务并修复；当前已上线的版本在新部署完成前继续服务。

## 本地预检

输出目录必须是仓库 `tmp/` 下的空目录，已有文件不会自动删除：

```bash
python3 scripts/build_pages.py --output-dir tmp/pages-preview/university-design-db
python3 -m http.server 8766 --bind 127.0.0.1 --directory tmp/pages-preview
```

打开 `http://127.0.0.1:8766/university-design-db/`，可验证与线上一致的项目子路径、JSON 分包、脚本和来源链接。构建不会联网或修改学校事实；`deployment.json` 记录本次构建的源提交。

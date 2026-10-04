# 在线素材目录

在线入口：[https://yangxiake.github.io/university-design-db/](https://yangxiake.github.io/university-design-db/)。浏览器直接搜索学校、筛选素材、查看配色与模板入口，并复制或下载单校JSON给AI。地址参数保存学校和筛选，分享单校地址时会保留这些条件。

本项目使用公开仓库的GitHub Pages和标准GitHub托管运行器；GitHub说明公开仓库可使用免费Pages，公开仓库的Actions运行免费。使用GitHub提供的域名，不购买服务器或自定义域名。说明见[创建Pages站点](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)。

## 发布内容

构建脚本`scripts/build_pages.py`将网页放到站点根目录，按固定列表发布6个页面/样式/脚本文件、检索目录与31个地区JSON，另附`.nojekyll`和`deployment.json`。当前共40个文件，约17.7 MB。`deployment.json`记录源提交、学校/地区数量、导出哈希及每个站点文件的哈希。

网站不包含本机图片缓存、原始校徽/模板/字体、研究日志、开发环境或测试文件。图形仍从记录的原来源载入，ZIP/PDF资源通过原入口获取；原站网络或浏览器限制仍可能导致图形预览失败。完整档案和页脚说明链接指向本次部署提交的GitHub文件；本地网页继续使用原相对路径。

## 同步和重新部署

源代码与资料保留在main，静态网站发布到`codex/gh-pages`分支。Pages设置使用`Deploy from a branch`，选择该分支与根目录`/`；GitHub自带的Pages构建和发布机制随该分支的推送更新站点。维护者同步已通过检查的版本，main推送本身不会直接更新网站。

维护者在完整源仓库提交并推送main，等待[Data quality](https://github.com/yangxiake/university-design-db/actions/workflows/quality.yml)的Python 3.9、3.13检查均成功，再运行：

```bash
python3 scripts/publish_pages.py
```

发布脚本需要已登录的GitHub CLI与Git。它核对仓库公开、工作区干净、远程main与HEAD一致、同一源提交的质量检查成功，再构建40个文件并普通推送发布分支。旧发布提交保留，不强制覆盖分支；已有分支必须包含可识别的站点清单。相同版本已发布时直接返回，不重复提交。

初次创建部署工作流曾被GitHub拒绝：当前OAuth登录缺少`workflow`权限。因此采用分支发布，未扩大登录权限，也未新增部署工作流。官方配置见[选择Pages发布来源](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。

本地预检使用Python标准库，输出目录必须是仓库`tmp/`下的空目录，已有文件不会自动删除：

```bash
python3 scripts/build_pages.py --output-dir tmp/pages-preview/university-design-db
python3 -m http.server 8766 --bind 127.0.0.1 --directory tmp/pages-preview
```

打开`http://127.0.0.1:8766/university-design-db/`，可验证与线上一致的项目子路径、JSON分包、脚本和来源链接。构建不会联网，也不会修改学校事实；预检中的`deployment.json`记录本地HEAD，正式工作流从干净的通过检查的提交构建。

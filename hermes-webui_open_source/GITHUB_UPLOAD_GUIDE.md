# Hermes WebUI - GitHub Upload Guide

## 📦 Open Source Package
位置: `D:\4. Web\HYCOforce web\0_workstation\2_Kilo\hermes_webui\hermes-webui_open_source\`

包含文件:
- **index.html** (64KB) - WebUI 主界面 (xterm.js + 双语切换 + 双服务器 + PTY + 模型管理)
- **proxy-server.py** (15KB) - 后端代理 (Hangzhou 本地 spawn + Tokyo SSH tunnel + WebSocket)
- **README.md** (4.2KB) - 中英文说明文档 (部署 + 配置 + 故障排查)
- **LICENSE** (1KB) - MIT License
- **temp.hycoforce.com.nginx** (1.9KB) - Nginx 配置示例
- **.gitignore** - Git 忽略规则

---

## 🚀 上传到 GitHub

### 方式 A: 手工上传 (适合一次性发布)

1. **访问 GitHub 并创建仓库**
   ```
   https://github.com/new
   仓库名: hermes-webui
   公开: Public
   ```

2. **下载 GitHub Desktop** (可选，方便操作)

3. **完成以下步骤**:
   ```bash
   # 方式1: 使用 Git Bash
   cd "D:\4. Web\HYCOforce web\0_workstation\2_Kilo\hermes_webui"

   # 初始化 Git 仓库 (如果还没有)
   git init
   git config user.name "Your Name"
   git config user.email "your@email.com"

   # 添加文件
   git add hermes-webui_open_source/*.html hermes-webui_open_source/*.py hermes-webui_open_source/*.md hermes-webui_open_source/*.license hermes-webui_open_source/*.nginx
   git commit -m "Release: Hermes WebUI v20260603"

   # 添加 GitHub 远程仓库
   git remote add origin https://github.com/[YourGitHubUsername]/hermes-webui.git

   # 推送到 GitHub
   git push -u origin main
   ```

4. **创建 GitHub Release**
   - 进入仓库页面
   - 点击 "Releases" → "Create a new release"
   - 版本号: `v20260603`
   - 标题: `Hermes WebUI v20260603 - 双服务器切换 + PTY 终端`
   - 上传 `hermes-webui_open_source/hermes-webui_v20260603.tar.gz` (如果需要)

---

### 方式 B: 使用 GitHub Desktop (适合频繁更新)

1. **安装 GitHub Desktop**
   - 下载: https://desktop.github.com

2. **创建 GitHub 仓库** (在 GitHub 网站完成)

3. **打开 GitHub Desktop**
   - File → Clone Repository → 选择本地文件夹
   - 选择 `hermes-webui_open_source`

4. **提交更改**
   - 显示更改 → Add all files → Commit
   - Commit message: `Release: Hermes WebUI v20260603`

5. **推送到 GitHub**
   - Push origin → 等待完成

6. **发布 Release**
   - Releases → New release → 填写版本号和描述

---

## ✨ GitHub 仓库优化建议

### 1. 添加 Topics (让更多开发者发现)
- #hermes
- #terminal
- #webui
- #hyperledger
- #blockchain
- #python

### 2. 添加 Auto Release (可选)
使用 GitHub Actions (`.github/workflows/release.yml`):
```yaml
name: Release
on:
  push:
    tags:
      - 'v*'
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: ncipollo/release-action@v1
        with:
          artifacts: 'dist/*'
          commitBody: 'Open source release v${{ github.ref_name }}'
```

### 3. 代码徽章 (可选)
在 README.md 顶部添加:
```markdown
![Build Status](https://github.com/[YourUsername]/hermes-webui/actions/workflows/release.yml/badge.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
```

---

## 📊 使用统计 (推荐)

添加到 README.md:
```markdown
## 📈 使用统计

- 支持 **两台** Hermes Agent Dashboard (杭州 + 东京)
- PTY 终端基于 **xterm.js** 和 **ptyprocess**
- 双服务器 **切换速度 < 100ms**
- 模型管理支持 **Provider CRUD** 完整功能
```

**后续可集成**: https://github.com/anuraghazra/github-readme-stats

---

## 💎 贡献指南

1. **Fork 仓库**
2. **创建分支**: `git checkout -b feature-name`
3. **提交更改**: `git commit -m 'Add feature'`
4. **推送到分支**: `git push origin feature-name`
5. **提交 Pull Request**

---

## 📞 问题反馈

GitHub Issues: https://github.com/[YourUsername]/hermes-webui/issues

---

## 🎯 下一步计划

- [ ] 添加 Docker 支持 (Dockerfile)
- [ ] 添加 k8s 部署清单 (deployment.yaml)
- [ ] 添加 Playwright 测试 (test_*.spec.ts)
- [ ] 添加中文/English 明显切换标识
- [ ] 添加更多模型预加载

---

**祝开源愉快!** 🎉

# 刷题记录 · 题目检索系统

一个用于 OI / 算法竞赛的**轻量级题目检索库**：只记录题名、难度、标签、链接，按条件组合快速筛选，体验类似洛谷的题单检索。数据持久化在本地 SQLite 数据库，单机运行、无需联网、无需注册。

![tech](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![tech](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)
![tech](https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E?logo=javascript&logoColor=black)
![license](https://img.shields.io/badge/AI--developed-100%25-green)

---

## 功能特性

- **记录四要素**：题名、难度（洛谷当前 8 档）、标签（洛谷官方 262 个算法标签）、题目跳转链接
- **组合检索**：难度精确筛选 + 标签「且 / 或」组合 + 题名搜索 + 多种排序
- **洛谷数据**：难度体系与配色对齐洛谷官方；标签来自洛谷官方标签接口的 `Algorithm` 分类
- **跳转链接**：手填网址后题名变为可点击链接，新标签页打开
- **13 套成套主题**：深色 8 套 + 浅色 5 套，切换时背景、面板、文字、主色一起变化（含 Catppuccin、Dracula、Nord、Gruvbox、Tokyo Night、One Dark、Rose Pine 等经典配色）
- **真数据库**：SQLite 本地文件持久化，换浏览器、清缓存都不丢数据
- **备份**：JSON 导入 / 导出
- **一键启动**：双击桌面脚本即可拉起服务并打开浏览器

---

## 使用方法

### Windows 一键启动（推荐）

1. 双击项目内的 `启动刷题记录.vbs`（或桌面上的同名快捷方式）
2. 脚本会自动检测服务是否已运行；未运行则后台拉起 Python 服务，然后打开浏览器
3. 浏览器访问 `http://127.0.0.1:8765/`

> 注意：本系统是 **C/S 架构**，必须通过本地服务访问，**不要直接双击 HTML 文件**（那样接口连不上）。

### 手动启动

```bash
cd D:\OI\刷题记录系统
python server.py
# 或
py -3 server.py
```

然后浏览器打开 <http://127.0.0.1:8765/>。

### 基本操作

- **添加题目**：右上角 `+ 添加题目` → 填题名、选难度、敲标签后回车（也可点选常用标签）、可选填链接 → 保存
- **筛选**：左侧栏按难度点选；标签支持「且 / 或」切换；顶部搜索框按题名过滤
- **点标签快筛**：直接点题目卡片上的标签，即可加入筛选条件
- **换主题**：右上角 `🎨 外观` → 切深浅模式、选主题风格
- **备份**：`导出备份` 存成 JSON；换环境后用 `导入` 恢复

### 环境要求

- Windows + Python 3.8 及以上（仅用标准库，无需 pip 安装任何依赖）
- 现代浏览器（Chrome / Edge / Firefox）

---

## 实现原理

### 整体架构

```
┌──────────────┐   fetch / REST API    ┌─────────────────┐   sqlite3    ┌──────────────┐
│  浏览器前端   │  ───────────────────▶ │  Python 本地服务 │ ────────────▶ │ problems.db  │
│ problem-tracker│ ◀─────────────────── │   server.py     │ ◀─────────── │  SQLite 数据库│
│    .html      │      JSON 响应        │ 127.0.0.1:8765  │              └──────────────┘
└──────────────┘                      └─────────────────┘
```

- **零依赖**：后端仅用 Python 标准库 `http.server` + `sqlite3`，前端是原生 HTML/CSS/JS，无构建步骤、无第三方包。
- **单机绑定**：服务监听 `127.0.0.1:8765`，只对本机开放，不暴露到网络。

### 数据库设计

三张规范化表：

| 表 | 说明 | 主要字段 |
|---|---|---|
| `problems` | 题目 | `id`, `name`, `difficulty`, `url`, `created` |
| `tags` | 标签（去重） | `id`, `name` |
| `problem_tags` | 题目-标签多对多关联 | `problem_id`, `tag_id` |

- 标签用关联表实现多对多，避免冗余存储，统计标签出现次数只需一次 JOIN。
- 加字段时用 `PRAGMA table_info` + `ALTER TABLE` 做平滑迁移（例如后来加 `url` 列），旧数据库升级不丢数据。

### 后端 API

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/problems` | 列出全部题目（含标签） |
| GET | `/api/stats` | 统计：题数、标签数、难度分布、数据库文件大小 |
| POST | `/api/problems` | 新增题目 |
| PUT | `/api/problems/{id}` | 更新题目 |
| DELETE | `/api/problems/{id}` | 删除单题 |
| DELETE | `/api/problems` | 清空全部 |
| POST | `/api/import` | 批量导入 |
| GET | `/api/export` | 导出为 JSON |

所有响应统一为 `{"ok": true, "data": ...}` 格式，前端 `fetch` 后统一拆包。

### 前端机制

- **筛选逻辑**：纯内存数组操作（`filter` / `sort`），数据量小时毫秒级完成，不查库。「且」= 包含所有选中标签，「或」= 包含任一。
- **主题系统**：13 套主题各自定义一组 CSS 变量（`--bg` / `--panel` / `--text` / `--accent` 等），切换只改 `data-theme` 属性，整套变量联动，背景一并改变。首屏脚本先读本地偏好再设置属性，避免闪烁。
- **标签补全**：262 个洛谷算法标签内嵌为常量，配合原生 `datalist` 与快捷标签面板输入。
- **难度兼容**：`DIFF_ALIAS` 映射旧难度名到新名称，旧记录自动迁移不失效。

### 洛谷数据是怎么来的

- 洛谷有反爬：首次请求返回 302 并下发 `C3VK` cookie，带 cookie 二次请求即可拿到完整页面。
- 标签数据来自官方接口 `https://www.luogu.com.cn/_lfe/tags`，返回全量标签的 `id / name / type / parent`。
- 该接口的 `types` 定义中，`type=2` 即 **Algorithm（算法）**，据此筛出 262 个算法标签。原始数据快照见 `luogu-tags-raw.json`。

---

## 项目结构

```
.
├── problem-tracker.html      # 前端单页（界面 + 逻辑 + 13 套主题）
├── server.py                 # Python 后端（REST API + SQLite）
├── 启动刷题记录.vbs           # Windows 一键启动器
├── luogu-tags-raw.json       # 洛谷官方标签原始快照（505 个标签）
└── README.md                 # 本文档
```

> `problems.db` 是运行时生成的用户数据文件，已加入 `.gitignore`，不会提交到仓库。

---

## AI 声明

**本项目完全由 AI 开发。**

从需求分析、架构设计、代码实现（前端、后端、数据库）、数据抓取、主题配色、到文档撰写与调试验证，全程由人工智能助手完成，无人工编写代码。项目作为 AI 辅助软件工程的实践示例开源，供学习交流使用。

---

## 许可证

本项目仅供个人学习与交流使用。洛谷相关标签与难度名称版权归洛谷所有；配色方案参考 Catppuccin、Dracula、Nord、Gruvbox、Tokyo Night、One Dark、Rose Pine 等开源主题项目。

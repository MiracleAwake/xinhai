# 心海前端原型

只调用心海 HTTP 接口，不直接读写 SQLite。开发时连 `frontend/.demo` 里的演示库，不连任何正式记忆库。

## 启动

```powershell
# 1. 演示后端（第一次会自动生成演示库）
.\run_demo_backend.ps1

# 2. 前端
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。Vite 把 `/api` 转发到 `http://127.0.0.1:8765`，所以后端不需要开 CORS。要换后端地址，设置环境变量 `XINHAI_API`。

重置演示数据：删除 `.demo` 文件夹，或运行 `python scripts/seed_demo.py`。

## 哪些是真的，哪些是模拟

| 部分 | 状态 |
|---|---|
| 记忆海面（检索 + Evidence） | 接真实接口 `/memories/evidence` |
| 候选审核（列表、确认、废弃） | 接真实接口 `/memories`、`/memories/confirm`、`/memories/forget` |
| 新建家人第 3 步「检查是否接通」 | 接真实接口：按新家人的分支查是否已有记录 |
| 截图与开关 | 接真实接口 `/memories/structured/compare` |
| 配置（当前、历史、差异） | 接真实只读接口；演示库里有 v1、v2 |
| 检查点 | 写入与列出历史都有接口（`POST /checkpoints`、`GET /checkpoints`）；**历史要先有真实 `session_id`**，现在还没接上 |
| 注册、登录、家庭组、客户端目录 | 模拟，存在浏览器 localStorage |
| 自定义分层、秘书起草收录规则 | 模拟；后端分层接口**已有 5 条**（`/layers`、`/layers/{id}/confirm`、`/layers/{id}/document` 等），前端一条未接 |
| 导入会话 | 只做展示；后端导入接口**已有 9 条**（`/imports`、`/imports/{id}/drafts`、`/imports/{id}/messages` 等），前端一条未接 |

页面上凡是模拟的部分都带「模拟」标记。

## 2026-11-18 交接

格温做到玻璃面外观和按钮手感后停手，后面由薇珈完善。外观参考过 `D:\Vega_workspace\2026-11-18-14-46-39\deepsea-memory.html`，没有改那份文件。

按钮目前是：按下从落点荡开淡蓝涟漪，悬停有一小块光跟着鼠标，按下会轻轻下沉。流光和磁吸没做。判据在格温经验库 **CODE-14**。

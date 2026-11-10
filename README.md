<div align="center">

# 🧾 发票OCR管理系统

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI Version](https://img.shields.io/badge/FastAPI-0.110-green.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/version-v2.0-orange.svg)](https://github.com/chiupam/invoiceOCR/releases)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-available-blue.svg)](https://hub.docker.com/r/chiupam/invoiceocr)
[![Coverage Status](https://img.shields.io/badge/coverage-80%25-green.svg)](https://github.com/chiupam/invoiceOCR/actions)

</div>

一个基于 **FastAPI** 的智能发票管理系统，支持发票图片/PDF上传与 OCR 识别，提供发票信息管理、数据导出及统计分析等功能。

支持三种票据类型（增值税发票 / 医疗票据 / 铁路电子客票），内置可插拔 OCR 后端回退链：**本地 pdfplumber 直提（免费、毫秒级）→ vLLM 通用视觉模型 → 腾讯云 OCR**。所有后端收敛到统一的 `formatted_data` 数据契约，前端与数据库无需感知后端差异。

## ✨ 功能特点

- 📤 发票图片和PDF文件上传，**异步识别**（上传即返回，后台处理，进度可查）
- 🧠 多后端 OCR 回退链：电子PDF优先本地直提（零成本），失败自动回退云端
- 🧾 多票据类型：增值税发票、医疗票据、火车票，自动路由到对应解析器
- 📄 电子PDF直接提取文本，扫描件走 OCR
- ✏️ 支持手动创建发票，无需上传图片
- 💾 发票数据结构化存储（含类型专属区块：医保信息/乘车信息）
- 📋 发票列表展示与多维度排序（金额/明细数/日期/号码）
- 🔎 发票详情查看与编辑、项目分类管理
- 📊 发票数据导出（CSV、Excel格式）
- 📈 发票统计分析与图表展示
- 🚀 生产部署：gunicorn + UvicornWorker + 健康检查（`/health`）
- 🔐 用户登录认证（bcrypt + 仅密码登录）、TOTP 两步验证
- 🛡️ 账户锁定保护（5次失败锁定15分钟 + 倒计时）、CSRF 双提交防护、登录限流
- 🗄️ Alembic 数据库迁移，表结构变更可版本化
- 📝 安全审计日志（`data/logs/security.log`）

## 🔄 v2.0 重写说明（FastAPI）

v2.0 将 Web 层从 Flask 整体重写为 FastAPI，核心改进：

| 维度 | v1.x (Flask) | v2.0 (FastAPI) |
|---|---|---|
| 上传识别 | 请求线程内同步执行，慢后端阻塞 20–60s | 异步任务：立即返回 task_id，后台识别，前端轮询 `/api/tasks/{id}` |
| Web 框架 | Flask 2 + 7 个扩展 | FastAPI + SQLAlchemy 2.0 + Pydantic 2 |
| 表结构演进 | `db.create_all()` | Alembic 迁移（存量库执行 `alembic stamp head` 一次性登记） |
| 认证/CSRF/限流 | Flask-Login / Flask-WTF / Flask-Limiter | 自研中间件（签名 cookie 会话、CSRF 双提交、内存限流） |
| 代码量 | app 层约 5200 行 | 约 2500 行，routes.py 拆分为 4 个 router |

**数据完全兼容**：v2.0 的表结构与 v1.x 一致（仅新增 `ocr_tasks` 任务表），现有 `data/invoices.db` 直接可用，无需迁移数据。解析核心（`core/`）保持框架无关，行为与 v1.x 一致，23 项净化夹具回归测试全部通过。

> ⚠️ v2.0 移除了 v1.4 的 Flask CLI 管理命令（`flask unlock-admin` / `reset-account` / `create-admin`）。应急解锁请直接操作数据库或将 `users` 表中对应账户的 `locked_until` 置空。

## 🚀 快速开始

### 🐳 使用 Docker（推荐）

#### 1️⃣ 部署步骤

```bash
git clone https://github.com/chiupam/invoiceOCR.git
cd invoiceOCR

# 可选：复制环境变量文件（SECRET_KEY 建议显式设置）
cp .env.example .env

docker-compose up -d
```

浏览器访问 http://localhost:5001 。首次访问会引导设置访问密码，登录后在「系统设置」配置 OCR 密钥。

#### 2️⃣ 常用命令

```bash
docker-compose logs -f        # 查看日志
docker-compose down           # 停止
docker-compose up -d --build  # 更新代码后重建
```

#### 3️⃣ 使用预构建镜像

```bash
# Docker Hub（最新 FastAPI 版本）
docker pull chiupam/invoiceocr:latest

# 运行容器
docker run -d -p 5001:5001 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/app/static/uploads \
  --name invoice_ocr chiupam/invoiceocr:latest
```

> 💾 两个卷挂载缺一不可：`/app/data` 存数据库与导出文件，`/app/app/static/uploads` 存发票原件。容器自带 `HEALTHCHECK`（探测 `/health`）。

#### 4️⃣ HTTPS 部署

反向代理终止 TLS 后，设置环境变量 `SECURE_COOKIES=true`，会话 cookie 将仅经加密连接发送。

### 💻 本地部署

```bash
# Python 3.12+
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest

# 运行测试（可选，验证解析器）
python -m pytest test/

# 启动开发服务器（uvicorn，默认 5001 端口，支持热重载）
python run.py
```

首次访问 http://localhost:5001 设置访问密码，然后到「系统设置」配置：

- **腾讯云 OCR**（SecretId/SecretKey，用于扫描件）
- **vLLM 后端**（可选，OpenAI 兼容接口，默认 SiliconFlow DeepSeek-OCR，可指向本地 Ollama/vLLM）

文本型电子PDF无需任何密钥，本地 pdfplumber 直接提取。

### 🗄️ 数据库迁移

```bash
# 空库：直接建表
alembic upgrade head

# 从 v1.x 升级（表已存在）：仅登记版本号
alembic stamp head
```

## 📂 项目结构

```
invoiceOCR/
├── app/                              # Web 应用（FastAPI）
│   ├── main.py                       # 应用工厂：中间件/路由/错误处理
│   ├── config.py                     # pydantic-settings 配置（env + .env）
│   ├── database.py                   # SQLAlchemy 2.0 engine/session
│   ├── models.py                     # ORM 模型（含 ocr_tasks 异步任务表）
│   ├── security.py                   # 会话/CSRF/flash cookie 签名
│   ├── deps.py                       # 依赖注入：登录态/CSRF 校验
│   ├── jinja.py                      # Jinja2 渲染（兼容模板 url_for）
│   ├── routers/                      # 路由层
│   │   ├── auth.py                   # 登录/设置/MFA/密码管理
│   │   ├── pages.py                  # 页面路由（仪表盘/上传/发票/项目/设置）
│   │   ├── api.py                    # JSON API（统计/任务轮询/维护）
│   │   └── health.py                 # 健康检查（免认证免限流）
│   ├── services/                     # 业务服务层（框架无关）
│   │   ├── ocr_service.py            # OCR 管线 + 异步任务执行
│   │   ├── stats_service.py          # 统计
│   │   └── export_service.py         # 导出与清理
│   ├── templates/ + static/          # Jinja2 模板与前端资源
├── core/                             # 解析核心（框架无关）
│   ├── doc_types/                    # 票据类型注册表（vat/medical/train）
│   ├── extractors/                   # OCR 后端回退链（local-pdf/vllm/tencent）
│   ├── invoice_formatter.py          # formatted_data 格式化
│   └── invoice_export.py             # 数据导出
├── migrations/                       # Alembic 迁移脚本
├── test/
│   ├── fixtures/blocks/              # 净化夹具（脱敏版面数据）
│   └── test_*_parser.py              # 解析器回归测试
├── docs/agents/                      # 架构文档（解析器/后端/夹具流程）
├── data/                             # 运行时数据（db/日志/导出，不入库）
├── alembic.ini                       # 迁移配置
├── gunicorn.conf.py                  # 生产服务器配置
├── docker-compose.yml
├── Dockerfile                        # 含 HEALTHCHECK
└── run.py                            # 开发入口（uvicorn）
```

## 🧠 多后端识别机制

上传文件后按以下顺序处理：

1. **本地直提**（仅 PDF）：pdfplumber 提取文本，核心字段完整则直接采用——免费、毫秒级
2. **所选 OCR 后端**：本地提取不完整时自动回退
   - `tencent`：腾讯云 OCR，按票据类型路由到对应接口
   - `vllm`：OpenAI 兼容的通用视觉模型（SiliconFlow / 本地 vLLM / Ollama）

识别结果统一为 `formatted_data` 契约，持久化到固定列 + `extra_data` JSON（医疗的医保信息、火车票的乘车信息）。

## 🔧 配置说明

所有配置通过 `.env`（复制自 `.env.example`）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `SECRET_KEY` | 会话签名密钥，**生产必须设置** | 留空则随机（重启后所有会话失效） |
| `SECURE_COOKIES` | HTTPS 部署设为 true | false |
| `DATABASE_URL` | 数据库连接 | SQLite `data/invoices.db` |
| `UPLOAD_FOLDER` / `OUTPUT_DIR` | 存储路径（Docker 指向持久卷） | 项目内目录 |
| `MAX_UPLOAD_MB` | 上传大小限制 | 16 |
| `TENCENT_SECRET_ID/KEY` | 腾讯云凭证（仅首次启动导入，之后在 Web 设置页管理） | 空 |
| `VLLM_OCR_ENDPOINT/API_KEY/MODEL` | vLLM 后端配置 | SiliconFlow DeepSeek-OCR |

## 🛠️ 开发者指南

- **架构文档**：`docs/agents/` 五篇（解析器架构、本地解析、夹具流程、票面布局、北京数电票族）
- **新增票据类型**：在 `core/doc_types/` 注册新 DocType（OCR action + 字段提取 + extra_data 区块）
- **新增解析回归**：向 `test/fixtures/blocks/` 添加净化夹具（禁止真实票面信息入库）
- **CI**：GitHub Actions 在 Release/手动触发时构建多架构镜像（amd64/arm64）推送 Docker Hub 与 GHCR

## 📝 许可证

MIT License

## 👤 作者

- [chiupam](https://github.com/chiupam)
- ✈️ Telegram: [@Chiupam](https://t.me/Chiupam)
- 📧 Email: [chiupam@126.com](mailto:chiupam@126.com)

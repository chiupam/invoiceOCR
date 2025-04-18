<div align="center">

# 🧾 发票OCR管理系统

[![Python Version](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/)
[![Flask Version](https://img.shields.io/badge/flask-2.0.1-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-available-blue.svg)](https://hub.docker.com/r/chiupam/invoiceocr)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Coverage Status](https://img.shields.io/badge/coverage-80%25-green.svg)](https://github.com/chiupam/invoiceOCR/actions)

</div>

一个基于Flask框架开发的智能发票管理系统，支持发票图片上传与OCR识别，提供发票信息管理、数据导出及统计分析等功能。系统采用腾讯云OCR API进行发票文字识别，实现发票信息的智能提取与处理。

## ✨ 功能特点

- 📤 发票图片和PDF文件上传与预览
- ✏️ 支持手动创建发票，无需上传图片
- 🔍 基于腾讯云OCR API的发票文字识别
- 📄 支持直接识别PDF发票第一页
- 💾 发票数据结构化处理与存储
- 📋 发票列表展示与多维度排序
- 🔎 发票详情查看与编辑
- 📁 项目分类管理功能
- 👁️ 发票图片与PDF预览功能
- 📊 发票数据导出（CSV、Excel格式）
- 📈 发票统计分析与图表展示
- 📱 响应式网页设计，适配多种设备
- ⏱️ 定时任务自动清理过期文件

## 🔄 最近更新

最新版本 v1.3 (2024.04.04)
- ✅ 添加手动创建发票功能，无需上传图片即可录入信息
- 🐛 修复未分类发票统计显示问题
- 🔧 添加对image_path为None的检查，避免模板渲染错误

查看完整的更新历史请参考 [CHANGELOG.md](CHANGELOG.md)

## 🚀 快速开始

### 🐳 使用 Docker

#### 1️⃣ 准备工作

确保已安装Docker和Docker Compose：
- [Docker安装指南](https://docs.docker.com/get-docker/)
- [Docker Compose安装指南](https://docs.docker.com/compose/install/)

#### 2️⃣ 部署步骤

##### (1) 克隆仓库并进入项目目录
```bash
git clone https://github.com/chiupam/invoiceOCR.git
cd invoiceOCR
```

##### (2) 创建环境变量文件（可选）
```bash
cp .env.example .env
# 仅需配置基本环境变量，API密钥通过Web界面配置
```

##### (3) 构建并启动容器
```bash
docker-compose up -d
```

##### (4) 访问应用
浏览器访问 http://localhost:5001 即可使用应用。首次访问时，系统会引导您完成腾讯云API密钥设置。

#### 3️⃣ 常用Docker命令

- **查看容器日志**
```bash
docker-compose logs -f
```

- **停止容器**
```bash
docker-compose down
```

- **重新构建（更新代码后）**
```bash
docker-compose up -d --build
```

#### 4️⃣ 使用预构建的Docker镜像

我们提供了多个镜像源以适应不同地区用户的需求：

##### 🔵 Docker Hub (推荐)

```bash
# 拉取最新版本
docker pull chiupam/invoiceocr:latest

# 拉取特定版本
docker pull chiupam/invoiceocr:v1.3

# 运行容器
docker run -d -p 5001:5001 -v $(pwd)/data:/app/data --name invoice_ocr chiupam/invoiceocr:latest
```

##### 🔷 GitHub Container Registry

```bash
# 拉取最新版本
docker pull ghcr.io/chiupam/invoiceocr:latest

# 拉取特定版本
docker pull ghcr.io/chiupam/invoiceocr:v1.3

# 运行容器
docker run -d -p 5001:5001 -v $(pwd)/data:/app/data --name invoice_ocr ghcr.io/chiupam/invoiceocr:latest
```

##### 💾 数据持久化

上面的命令使用了卷挂载 `-v $(pwd)/data:/app/data` 来保证数据在容器重启后不会丢失。您可以根据需要修改本地路径。

### 💻 本地部署

#### 1️⃣ 克隆项目

```bash
git clone https://github.com/chiupam/invoiceOCR.git
cd invoiceOCR
```

#### 2️⃣ 创建并激活虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 激活虚拟环境 (Windows)
# .venv\Scripts\activate
```

激活后，命令行前面会出现`(.venv)`前缀，表示当前处于虚拟环境中。后续所有命令都应在此环境中执行。

#### 3️⃣ 安装依赖

```bash
# 确保在虚拟环境中执行
(.venv) pip3 install -r requirements.txt
```

#### 4️⃣ 基本环境配置

创建 `.env` 文件（可以复制 `.env.example` 并根据需要修改）：

```bash
# 复制示例配置
(.venv) cp .env.example .env
```

注意：与旧版本不同，API密钥现在不需要在环境变量中配置，而是在Web界面中设置。

#### 5️⃣ 运行应用

```bash
(.venv) python3 run.py
```

应用将在 http://127.0.0.1:5001/ 运行。首次运行时，系统会自动初始化数据库并引导您完成必要的设置。

#### 6️⃣ 首次访问配置

首次访问系统时，会自动跳转到设置页面，需要配置以下信息：

1. 腾讯云OCR API密钥（SecretId和SecretKey）
   - 可在[腾讯云控制台](https://console.cloud.tencent.com/cam/capi)获取
   - 需要开通腾讯云OCR服务（增值税发票识别）

配置完成后，即可开始使用系统的所有功能。

#### 7️⃣ 退出虚拟环境（完成使用后）

```bash
(.venv) deactivate
```

#### ❓ 常见问题解决

- **依赖安装失败**：尝试更新pip后再安装 `python3 -m pip install --upgrade pip`
- **数据库初始化错误**：确认是否有足够权限创建文件，或检查data目录是否存在
- **OCR识别失败**：检查`.env`文件中的腾讯云API密钥是否正确

## 📂 项目结构

```
InvoiceOCR/
├── app/                          # Web应用主目录
│   ├── static/                   # 静态资源
│   │   ├── css/                  # CSS样式
│   │   │   └── style.css         # 全局样式表
│   │   ├── js/                   # JavaScript文件
│   │   │   ├── edit_invoice.js   # 发票编辑页面脚本
│   │   │   ├── index.js          # 首页脚本
│   │   │   ├── main.js           # 主要公共脚本
│   │   │   └── upload.js         # 上传页面脚本
│   │   └── uploads/              # 上传的发票图片存储目录
│   ├── templates/                # HTML模板
│   │   ├── errors/               # 错误页面模板
│   │   │   ├── 404.html          # 404错误页面
│   │   │   └── 500.html          # 500错误页面
│   │   ├── base.html             # 基础布局模板
│   │   ├── index.html            # 首页模板
│   │   ├── invoice_create.html   # 发票创建页面
│   │   ├── invoice_detail.html   # 发票详情页面
│   │   ├── invoice_edit.html     # 发票编辑页面
│   │   ├── project_detail.html   # 项目详情页面
│   │   ├── project_form.html     # 项目编辑表单
│   │   ├── project_list.html     # 项目列表页面
│   │   ├── settings.html         # 设置页面
│   │   └── upload.html           # 上传页面
│   ├── __init__.py               # 应用初始化
│   ├── config.py                 # 应用配置
│   ├── models.py                 # 数据模型
│   ├── routes.py                 # 路由定义
│   └── utils.py                  # 辅助函数
├── core/                         # 核心功能模块
│   ├── __init__.py               # 模块初始化
│   ├── invoice_export.py         # 发票数据导出功能
│   ├── invoice_formatter.py      # 发票数据格式化
│   ├── ocr_api.py                # OCR API调用功能
│   ├── ocr_process.py            # OCR结果处理
│   └── README.md                 # 核心模块说明文档
├── data/                         # 数据存储目录
│   ├── invoices.db               # SQLite数据库文件
│   ├── output/                   # 导出文件存储目录
│   └── README.md                 # 数据目录说明文档
├── tools/                        # 工具脚本目录
│   ├── clean_temp_files.py       # 临时文件清理工具
│   ├── db_backup.py              # 数据库备份工具
│   ├── db_init.py                # 数据库初始化脚本
│   ├── db_query.py               # 数据库查询工具
│   ├── generate_test_data.py     # 测试数据生成工具
│   └── README.md                 # 工具脚本说明文档
├── test/                         # 测试目录
│   ├── fixtures/                 # 测试数据目录
│   │   └── invoices/             # 测试发票图片
│   └── README.md                 # 测试说明文档
├── .env.example                  # 环境变量示例文件
├── .gitignore                    # Git忽略文件
├── docker-compose.yml            # Docker Compose配置
├── Dockerfile                    # Docker构建文件
├── LICENSE                       # 许可证文件
├── README.md                     # 项目说明文档
├── requirements.txt              # 项目依赖
└── run.py                        # 应用启动脚本
```

## 🔧 配置说明

### 上传发票

1. 点击左侧导航栏中的"上传发票"
2. 选择一个项目分类（可选）
3. 拖拽发票图片或PDF文件到上传区域，或点击选择文件
4. 系统会自动识别并处理发票内容（对于PDF文件，会识别第一页）
5. 上传后自动跳转到发票详情页进行查看和编辑

### 项目管理

1. 点击左侧导航栏中的"项目管理"
2. 可以创建、编辑、删除项目
3. 点击项目卡片查看该项目下的所有发票
4. 未分类发票会显示在"未分类"区域

### 查看发票列表

- 在首页可以看到所有上传的发票列表
- 可以通过点击表头排序发票
- 控制台上方显示统计数据和图表
- 可以根据项目筛选发票列表

### 发票详情与编辑

- 点击发票列表中的发票行即可查看详情
- 点击发票图片可以在弹窗中查看大图，支持放大缩小功能
- 对于PDF文件，会显示PDF阅读器方便查看
- 点击"编辑"按钮修改发票信息，所有金额字段会自动处理货币符号
- 点击"删除"按钮删除发票

### 导出功能

在发票详情页，可以选择导出格式（CSV或Excel）导出发票数据。
在项目详情页，可以导出整个项目的发票数据为Excel。

### 清理导出文件

首页提供"清理导出文件"按钮，可以手动清理已导出的临时文件。
系统还会自动定期（每天凌晨3点）清理过期的导出文件。

## 🛠️ 开发者指南

### GitHub Actions 配置

本项目使用GitHub Actions自动构建和发布Docker镜像。如果您fork了本项目并希望启用自动构建，需要配置以下GitHub Secrets:

#### 1. 访问GitHub仓库设置

- 前往您的GitHub仓库
- 点击顶部的"Settings"选项卡
- 在左侧菜单中找到"Security"部分下的"Secrets and variables"
- 选择"Actions"

#### 2. 添加必要的Secrets

需要添加以下Secret以启用Docker Hub发布:

| Secret名称 | 说明 | 获取方式 |
|----------|------|---------|
| `DOCKERHUB_USERNAME` | Docker Hub用户名 | 您的Docker Hub账号用户名 |
| `DOCKERHUB_TOKEN` | Docker Hub访问令牌 | 在Docker Hub → Account Settings → Security中创建 |

#### 3. 获取Docker Hub访问令牌

1. 登录[Docker Hub](https://hub.docker.com/)
2. 点击右上角头像 → Account Settings → Security
3. 点击"New Access Token"按钮
4. 输入描述（如"GitHub Actions"）
5. 选择适当的权限（至少需要"Read & Write"权限）
6. 点击"Generate"生成令牌
7. **重要**: 立即复制生成的令牌，它只会显示一次

#### 4. 验证配置

配置完成后，每次发布新Release或手动触发工作流时，将自动构建并推送Docker镜像到您的Docker Hub账号。

## 📝 许可证

MIT License 

## 👤 作者

- [chiupam](https://github.com/chiupam)

## 🙏 致谢

感谢您的使用和反馈！如果您有任何问题或建议，请随时联系我们。 
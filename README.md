# InvoiceOCR

[![Python Version](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/)
[![Flask Version](https://img.shields.io/badge/flask-2.0.1-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-available-blue.svg)](https://hub.docker.com/r/chiupam/invoiceocr)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Coverage Status](https://img.shields.io/badge/coverage-80%25-green.svg)](https://github.com/chiupam/invoiceOCR/actions)

# 📄 发票OCR管理系统

一个基于Flask的发票OCR识别和管理系统，可以上传发票图片，自动识别提取信息，并提供管理、导出和统计功能。

## 🌟 功能特点

- 发票图片上传与预览
- 基于腾讯云OCR API的发票文字识别
- 发票数据结构化处理与存储
- 发票列表展示与多维度排序
- 发票详情查看与编辑
- 项目分类管理功能
- 发票图片预览与缩放功能
- 发票数据导出（CSV、Excel格式）
- 发票统计分析与图表展示
- 响应式网页设计，适配多种设备
- 定时任务自动清理过期文件
- 一键更新所有发票数据功能

## 🚀 快速开始

### 使用 Docker

#### 1. 准备工作

确保已安装Docker和Docker Compose：
- [Docker安装指南](https://docs.docker.com/get-docker/)
- [Docker Compose安装指南](https://docs.docker.com/compose/install/)

#### 2. 部署步骤

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

#### 3. 常用Docker命令

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

### 本地部署

#### 1. 克隆项目

```bash
git clone https://github.com/chiupam/invoiceOCR.git
cd invoiceOCR
```

#### 2. 创建并激活虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 激活虚拟环境 (Windows)
# .venv\Scripts\activate
```

激活后，命令行前面会出现`(.venv)`前缀，表示当前处于虚拟环境中。后续所有命令都应在此环境中执行。

#### 3. 安装依赖

```bash
# 确保在虚拟环境中执行
(.venv) pip3 install -r requirements.txt
```

#### 4. 基本环境配置

创建 `.env` 文件（可以复制 `.env.example` 并根据需要修改）：

```bash
# 复制示例配置
(.venv) cp .env.example .env
```

注意：与旧版本不同，API密钥现在不需要在环境变量中配置，而是在Web界面中设置。

#### 5. 运行应用

```bash
(.venv) python3 run.py
```

应用将在 http://127.0.0.1:5001/ 运行。首次运行时，系统会自动初始化数据库并引导您完成必要的设置。

#### 6. 首次访问配置

首次访问系统时，会自动跳转到设置页面，需要配置以下信息：

1. 腾讯云OCR API密钥（SecretId和SecretKey）
   - 可在[腾讯云控制台](https://console.cloud.tencent.com/cam/capi)获取
   - 需要开通腾讯云OCR服务（增值税发票识别）

配置完成后，即可开始使用系统的所有功能。

#### 7. 退出虚拟环境（完成使用后）

```bash
(.venv) deactivate
```

#### 常见问题解决

- **依赖安装失败**：尝试更新pip后再安装 `python3 -m pip install --upgrade pip`
- **数据库初始化错误**：确认是否有足够权限创建文件，或检查data目录是否存在
- **OCR识别失败**：检查`.env`文件中的腾讯云API密钥是否正确

## 📚 项目结构

```
InvoiceOCR/
├── app/                        # Web应用主目录
│   ├── static/                 # 静态资源
│   │   ├── css/                # CSS样式
│   │   ├── js/                 # JavaScript文件
│   │   └── uploads/            # 上传的发票图片存储目录
│   ├── templates/              # HTML模板
│   ├── __init__.py            # 应用初始化
│   ├── config.py              # 应用配置
│   ├── models.py              # 数据模型
│   ├── routes.py              # 路由定义
│   └── utils.py               # 辅助函数
├── core/                       # 核心功能模块
│   ├── __init__.py            # 模块初始化
│   ├── ocr_api.py             # OCR API调用功能
│   ├── invoice_formatter.py   # 发票数据格式化
│   └── invoice_export.py      # 发票数据导出功能
├── data/                       # 数据存储目录
│   ├── invoices.db            # SQLite数据库文件
│   └── output/                # 导出文件存储目录
├── tools/                      # 工具脚本目录
│   ├── db_init.py             # 数据库初始化脚本
│   └── db_query.py            # 数据库查询工具
├── tests/                      # 测试目录
├── .gitignore                 # Git忽略文件
├── README.md                  # 项目说明文档
├── requirements.txt           # 项目依赖
└── run.py                     # 应用启动脚本
```

## 🔧 配置说明

### 上传发票

1. 点击左侧导航栏中的"上传发票"
2. 选择一个项目分类（可选）
3. 拖拽发票图片到上传区域或点击选择文件
4. 系统会自动识别并处理发票内容
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

- 点击发票列表中的"查看"按钮查看详情
- 点击发票图片可以在弹窗中查看大图，支持放大缩小功能
- 点击"编辑"按钮修改发票信息
- 点击"删除"按钮删除发票

### 导出功能

在发票详情页，可以选择导出格式（CSV或Excel）导出发票数据。
在项目详情页，可以导出整个项目的发票数据为Excel。

### 一键更新所有发票

首页提供"更新所有发票"按钮，可以从已保存的JSON数据中重新提取并更新所有发票信息。

### 清理导出文件

首页提供"清理导出文件"按钮，可以手动清理已导出的临时文件。
系统还会自动定期（每天凌晨3点）清理过期的导出文件。

## 📝 许可证

MIT License 

## 👤 作者

- [chiupam](https://github.com/chiupam)

## 🙏 致谢

感谢您的使用和反馈！如果您有任何问题或建议，请随时联系我们。 
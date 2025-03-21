# 发票OCR管理系统

一个基于Flask的发票OCR识别和管理系统，可以上传发票图片，自动识别提取信息，并提供管理、导出和统计功能。

## 关于项目

- 项目名称：InvoiceOCR
- 仓库地址：https://github.com/chiupam/invoiceOCR
- 开发工具：使用Cursor进行开发

## 功能特点

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

## 技术栈

- **后端框架**：Flask
- **数据库**：SQLAlchemy + SQLite
- **前端**：Bootstrap 5 + Chart.js + Font Awesome
- **OCR服务**：腾讯云OCR API
- **任务调度**：Flask-APScheduler

## 安装部署

本项目支持两种部署方式：本地部署和Docker部署。

### 方式一：本地部署（使用虚拟环境）

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

#### 4. 配置环境变量

创建 `.env` 文件（可以复制 `.env.example` 并填写您自己的值）：

```bash
# 复制示例配置
(.venv) cp .env.example .env

# 编辑配置文件
(.venv) nano .env  # 或使用其他编辑器
```

设置以下必要的环境变量：

```
FLASK_APP=run.py
FLASK_ENV=development
TENCENT_SECRET_ID=你的腾讯云SecretId
TENCENT_SECRET_KEY=你的腾讯云SecretKey
```

**注意**：请勿将包含实际API密钥的`.env`文件提交到Git仓库！

#### 5. 运行应用

```bash
(.venv) python3 run.py
```

应用将在 http://127.0.0.1:5001/ 运行。系统会自动检测并初始化数据库（如果是首次运行）。

#### 6. 退出虚拟环境（完成使用后）

```bash
(.venv) deactivate
```

#### 常见问题解决

- **依赖安装失败**：尝试更新pip后再安装 `python3 -m pip install --upgrade pip`
- **数据库初始化错误**：确认是否有足够权限创建文件，或检查data目录是否存在
- **OCR识别失败**：检查`.env`文件中的腾讯云API密钥是否正确

### 方式二：Docker部署

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

##### (2) 创建环境变量文件
```bash
cp .env.example .env
# 编辑.env文件，填入腾讯云OCR API密钥
```

##### (3) 构建并启动容器
```bash
docker-compose up -d
```

##### (4) 访问应用
浏览器访问 http://localhost:5001 即可使用应用。系统会自动检测并初始化数据库（如果是首次运行）。

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

## 项目结构

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

## 使用说明

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

## 特色功能

### 自动识别发票信息

系统利用腾讯云OCR API自动识别发票上的文字信息，包括：
- 发票代码和号码
- 开票日期
- 销售方和购买方信息
- 金额和税额
- 发票商品明细

### 项目分类管理

- 创建不同的项目对发票进行分类管理
- 每个项目提供单独的统计信息
- 快速筛选查看特定项目的发票

### 图片预览功能

- 发票详情页点击图片可以打开预览模态框
- 支持放大/缩小/重置功能
- 可以在新窗口打开原始图片

### 数据统计与可视化

- 总发票数量和金额统计
- 当月发票数量和金额统计
- 按月统计发票数量和金额（图表展示）
- 发票类型分布统计（饼图展示）

### 自动化任务

- 自动清理过期导出文件
- 发票信息自动更新功能
- 数据备份管理

## 命令行工具

系统提供了一些有用的命令行工具：

```bash
# 初始化数据库
python3 tools/db_init.py [--drop]

# 查询数据库
python3 tools/db_query.py

# 清理过期文件
flask cleanup --days=7
```

## API接口

系统提供了JSON API接口：

- `/api/statistics` - 获取发票统计数据
- `/api/update-all-invoices` - 更新所有发票数据
- `/api/cleanup-exported-files` - 清理导出的文件

## 开发者

- [chiupam](https://github.com/chiupam)

## 许可证

MIT License 
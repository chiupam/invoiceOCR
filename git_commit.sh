#!/bin/bash
cd /Users/chiupam/Project/invoiceOCR
git add -A
git commit -F /dev/stdin << 'EOF'
chore: 基础稳定性修复与环境配置重构

- 安全修复: 开放重定向漏洞/事务原子性/Session清除
- 连接管理: OCR API连接泄漏修复/3次重试机制
- 路由重构: 提取blueprints模块精简约13行代码
- 数据库迁移: 引入Alembic支持schema版本管理
- 质量保障: 新增60个pytest测试/pyflakes零问题
- 代码清理: 移除10文件30+未使用导入/6未使用依赖
- 环境配置: development/testing/production动态切换
- 部署增强: Docker生产模式/healthcheck/安全检查
- 上传优化: 单文件自动跳转详情页/批量进度反馈
- 置信度提示: OCR结果各字段置信度可视化
- 重新识别: 发票详情页支持重新OCR识别
- 初始设置: 首次使用流程整合腾讯云API配置向导
- 失败展示: 完善上传失败信息展示
- 新增目录: app/blueprints/ migrations/ tests/
- 移除文件: core/ocr_process.py test/README.md
- 移除依赖: requests opencv-python PyPDF2 xlsxwriter email-validator pytz
EOF

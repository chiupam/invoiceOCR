# 更新日志 | Changelog

## 版本历史

### v1.3 (最新版本)
#### 💡 新增功能
- **手动创建发票**: 无需上传图片即可直接录入发票信息
- **项目详情优化**: 完善了项目详情页面和导航逻辑

#### 🛠 问题修复
- 修复未分类发票统计显示问题，确保准确计算未分类发票数量
- 添加对image_path为None的检查，避免模板渲染错误
- 修复JS脚本末尾的语法错误
- 优化明细项添加和编辑功能

### v1.2
#### 💡 新增功能
- **PDF文件支持**: 现在可以直接上传PDF格式的发票文件进行识别

#### 🔧 优化改进
- 优化发票编辑功能，改进金额字段的处理

#### 🛠 问题修复
- 修复发票详情页面的图片加载问题

### v1.1
#### 💡 新增功能
- **发票号码搜索与排序**: 增加了按发票号码搜索和排序的功能
- **项目文档更新**: 增加了更详细的项目文档和工具脚本
- **目录结构优化**: 添加了各目录的README文件，使项目结构更清晰

#### 🔧 优化改进
- **Docker优化**: 添加清华pip源，改进文件复制逻辑
- **界面体验提升**: 优化表格排序按钮样式和交互体验
- **前端功能改进**: 优化图片懒加载、上传流程和分页逻辑
- **文档美化**: 美化README.md，添加徽章和表情符号

#### 🛠 问题修复
- 修复项目详情页金额显示问题，正确处理带有货币符号的金额字符串
- 删除二维码识别功能，解决zbar库相关依赖问题

### v1.0 (首次发布)
#### 🚀 首次发布
增值税发票OCR识别与管理系统正式发布！

#### 💡 核心功能
- **图片上传识别**: 支持上传发票图片并进行OCR识别
- **信息管理**: 查看和编辑发票信息
- **列表展示**: 基本的发票列表展示功能
- **图片预览**: 发票图片预览功能

#### 🔧 基础功能
- **Docker支持**: 添加Docker部署支持，便于快速部署
- **自动初始化**: 自动数据库初始化功能
- **系统设置**: 支持在Web界面配置API密钥
- **拖放上传**: 支持拖放方式上传图片

## 即将推出

在未来的版本中，我们计划添加以下功能：

- 用户认证与权限管理
- 多种发票类型支持
- 数据分析与报表生成
- 数据导入功能
- 自定义发票分类规则
- API接口开放，支持第三方集成 
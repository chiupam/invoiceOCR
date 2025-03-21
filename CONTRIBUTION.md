# 贡献指南

感谢您考虑为发票OCR管理系统做出贡献！以下是参与项目开发的指南。

## 如何贡献

您可以通过以下几种方式为项目做出贡献：

1. **提交Bug报告**：如果您发现了Bug，请在GitHub Issues中提交详细的报告。
2. **功能建议**：如果您有新功能的想法，也可以在Issues中提出。
3. **提交Pull Request**：您可以直接修复Bug或实现新功能，然后提交Pull Request。

## 开发流程

1. Fork本仓库到您的GitHub账户
2. 克隆您的Fork到本地：`git clone https://github.com/chiupam/InvoiceOCR.git`
3. 创建开发分支：`git checkout -b feature/your-feature-name`
4. 进行代码修改
5. 提交更改：`git commit -am '添加新功能：功能描述'`
6. 推送到您的Fork：`git push origin feature/your-feature-name`
7. 在GitHub上创建Pull Request

## 代码规范

- 遵循PEP 8 Python编码规范
- 为函数和类添加文档字符串(docstrings)
- 合理命名变量和函数
- 保持代码简洁，易于理解

## 测试

- 在提交代码前，请确保所有测试通过
- 为新功能添加相应的测试用例
- 可以运行`pytest`来执行测试

## 提交规范

提交信息应简洁明了，并符合以下格式：

- `feat`: 新功能
- `fix`: 修复Bug
- `docs`: 文档更新
- `style`: 代码风格调整（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具变动

例如：`fix: 修复发票导出时文件名错误的问题`

## Pull Request流程

1. 确保您的PR描述清楚地说明了所做的更改及其原因
2. 如果PR解决了某个Issue，请在描述中引用该Issue
3. PR应包含必要的测试用例
4. 所有测试必须通过
5. 代码应符合项目的代码规范
6. 确保您的分支与主分支是最新的

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/chiupam/InvoiceOCR.git
cd InvoiceOCR

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或者
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖
```

## 许可证

通过贡献您的代码，您同意您的贡献将在MIT许可下发布。 
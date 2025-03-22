# 测试目录 (Test Directory)

本目录用于存放系统测试相关的代码、数据和文档。

## 当前状态

目前测试目录是空的，尚未实现自动化测试。这里提供了测试结构建议，作为未来开发的参考。

## 建议的目录结构

```
test/
├── fixtures/           # 测试固定数据，如样本发票图片、JSON响应等
├── unit/               # 单元测试
├── integration/        # 集成测试
├── conftest.py         # pytest配置文件
└── README.md           # 本文档
```

## 建议的测试实现

### 单元测试

建议优先实现以下单元测试：

- `test_invoice_formatter.py` - 测试发票格式化功能
- `test_ocr_api.py` - 测试OCR API接口
- `test_utils.py` - 测试工具函数

### 集成测试

建议实现的关键集成测试：

- `test_upload_process.py` - 测试完整的上传识别流程
- `test_export_process.py` - 测试导出功能流程

## 测试框架建议

推荐使用pytest作为测试框架，使用方法：

```bash
# 安装pytest
pip3 install pytest pytest-cov

# 运行测试（实现后）
python3 -m pytest
```

## 测试编写指南

1. 每个测试函数应专注于测试一个功能点
2. 使用有意义的名称命名测试函数，如 `test_format_invoice_extracts_correct_fields`
3. 准备测试数据文件放在 `fixtures/` 目录中
4. 测试应该是独立的，不依赖于其他测试的执行顺序

## 下一步工作

1. 创建基本的测试目录结构
2. 为核心功能添加单元测试
3. 实现持续集成，在代码提交时自动运行测试 
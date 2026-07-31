"""
发票OCR核心功能模块

包含：
- OCR API调用
- 发票数据格式化
- 发票数据导出

Importing this package eagerly registers the built-in document types
(vat, …) via ``core.doc_types``. Modules that need the registry can
simply ``import core`` or ``import core.doc_types`` — the side-effect is
intentional so that plug-in style DocType modules added later are picked
up without having to touch call sites.
"""

# Eager-register built-in document types (vat, …).
import core.doc_types  # noqa: F401

# 发票OCR系统核心模块

本目录包含发票OCR系统的核心功能模块，负责OCR识别、数据格式化和处理等关键功能。

## 目录结构

```
core/
├── __init__.py          # 包初始化文件
├── ocr_api.py           # OCR API调用模块
├── invoice_formatter.py # 发票数据格式化模块
├── invoice_export.py    # 发票导出功能模块
├── ocr_process.py       # OCR处理核心功能
└── README.md           # 本文档
```

## 系统工作流程

### 总体流程图

```
用户上传发票 → 临时保存 → OCR识别 → 数据格式化 → 检查重复 → 保存数据和图片 → 返回结果
```

### 详细流程说明

#### 1. 前端上传流程

1. **用户通过前端界面上传发票图片**：
   - 用户在`/upload`页面选择发票图片文件并提交
   - 可以选择关联的项目ID
   - 前端代码位于`app/templates/upload.html`和`app/static/js/upload.js`

2. **前端表单提交**：
   - 支持常规表单提交和AJAX方式提交
   - AJAX提交时会显示上传进度
   - 处理响应并提示用户结果

#### 2. 后端接收和初步处理

1. **接收和验证文件**：
   - `app/routes.py`中的`upload()`函数接收文件
   - 验证文件类型是否在允许列表中（如PNG、JPG）
   - 生成临时文件名并保存为带`temp_`前缀的临时文件
   
   ```python
   # 安全处理文件名
   filename = secure_filename(file.filename)
   
   # 创建文件保存目录
   upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
   
   # 先保存临时文件进行识别
   temp_file_path = os.path.join(upload_folder, "temp_" + filename)
   file.save(temp_file_path)
   ```

2. **调用处理函数**：
   - 调用`app/utils.py`中的`process_invoice_image()`处理图片文件
   - 传递临时文件路径和可选的项目ID
   
   ```python
   # 处理发票图片
   result = process_invoice_image(temp_file_path, project_id=project_id)
   ```

#### 3. OCR识别流程 (core/ocr_api.py)

1. **初始化OCR客户端**：
   - 创建`OCRClient`实例
   - 从环境变量或数据库获取腾讯云API凭证
   
   ```python
   # 创建OCR API客户端
   ocr_api = OCRClient()
   
   # OCRClient初始化
   def __init__(self):
       # 获取API凭证
       secret_id, secret_key = get_api_credentials()
       self.cred = credential.Credential(secret_id, secret_key)
       # ... 其他初始化代码
   ```

2. **调用OCR API识别发票**：
   - 读取图片内容并转为Base64编码
   - 调用腾讯云OCR API的`VatInvoiceOCR`接口
   - 获取返回的JSON结果
   
   ```python
   # 调用OCR API识别发票
   response_json = ocr_api.recognize_vat_invoice(image_path=image_path)
   
   # OCR API调用
   def recognize_vat_invoice(self, image_path=None, image_url=None, image_base64=None):
       action = "VatInvoiceOCR"
       # ... 处理图片数据
       return self._call_api(action, request_data)
   ```

#### 4. 发票数据格式化 (core/invoice_formatter.py)

1. **格式化OCR结果**：
   - 使用`InvoiceFormatter.format_invoice_data()`处理原始OCR结果
   - 根据发票类型（专票或普票）进行不同格式处理
   
   ```python
   # 格式化发票数据
   formatted_data = InvoiceFormatter.format_invoice_data(json_string=response_json)
   
   # 判断发票类型并格式化
   if "VatInvoiceInfos" in response_json["Response"]:
       if "普通发票" in invoice_type:
           logger.info("识别为增值税普通发票，使用普通发票格式化")
           return InvoiceFormatter._format_general_invoice(response_json)
       else:
           logger.info("识别为增值税专用发票，使用专用发票格式化")
           return InvoiceFormatter._format_vat_invoice(response_json)
   ```

2. **提取关键信息**：
   - 从格式化后的数据中提取发票代码、号码、金额等关键信息
   - 标准化日期和金额格式
   
   ```python
   invoice_data = {
       'invoice_code': formatted_data.get('基本信息', {}).get('发票代码', ''),
       'invoice_number': formatted_data.get('基本信息', {}).get('发票号码', ''),
       'invoice_type': formatted_data.get('基本信息', {}).get('发票类型', ''),
       # ... 其他字段
   }
   ```

#### 5. 发票查重和保存 (app/utils.py)

1. **检查发票唯一性**：
   - 检查是否成功识别出发票代码和号码
   - 如无法识别，保存一个失败副本，返回失败信息
   - 查询数据库检查是否已有相同代码和号码的发票
   
   ```python
   # 检查是否成功识别出发票代码和号码
   if not invoice_code or not invoice_number:
       # ... 处理识别失败的情况
       
   # 检查是否已存在相同代码和号码的发票
   existing_invoice = Invoice.query.filter_by(
       invoice_code=invoice_code,
       invoice_number=invoice_number
   ).first()
   ```

2. **保存发票图片和数据**：
   - 使用发票代码和号码生成新的文件名
   - 将临时文件移动到正式位置并删除临时文件
   - 创建新的`Invoice`数据库记录
   - 保存发票相关的商品项目信息到`InvoiceItem`表
   - 保存完整的JSON数据到数据库
   
   ```python
   # 使用发票代码和号码创建新的文件名
   new_filename = f"{invoice_code}{invoice_number}{os.path.splitext(filename)[1]}"
   
   # 创建新发票记录
   invoice = Invoice(
       invoice_code=invoice_data.get('invoice_code', ''),
       invoice_number=invoice_data.get('invoice_number', ''),
       # ... 其他字段
   )
   db.session.add(invoice)
   db.session.commit()
   ```

#### 6. 响应处理 (app/routes.py)

1. **返回处理结果**：
   - 如成功，返回成功消息和发票ID
   - 如失败，返回失败原因
   
2. **AJAX请求的特殊处理**：
   - 检测请求头判断是否为AJAX请求
   - 返回包含发票ID、代码和号码的JSON响应
   
   ```python
   # 检查是否为XHR请求（AJAX）
   if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
       response_data = {
           'success': True,
           'message': '发票上传和识别成功',
           'invoice_id': invoice_id,
           'invoice_code': invoice.invoice_code,
           'invoice_number': invoice.invoice_number
       }
       return jsonify(response_data)
   ```

### 处理专票和普票的区别

系统能够处理两种主要类型的发票：增值税专用发票（专票）和增值税普通发票（普票）：

1. **识别差异**：
   - 系统通过检查OCR返回的发票类型字段来区分专票和普票
   - 根据发票类型调用不同的格式化方法

2. **数据结构差异**：
   - 专票包含完整的销售方和购买方信息
   - 普票可能缺少部分字段或使用不同的字段名称
   - 系统对普票缺失的发票代码进行特殊处理（从发票号码提取）

3. **格式化处理**：
   - 专票使用`_format_vat_invoice`方法处理
   - 普票使用`_format_general_invoice`方法处理
   - 两种处理方法生成统一的数据结构，方便后续存储和展示

## 关键技术点

1. **OCR API调用**：
   - 使用腾讯云OCR API进行发票识别
   - 封装API调用过程，包括鉴权、签名等
   - 支持多种图片输入方式（本地路径、URL、Base64）

2. **数据格式化**：
   - 将复杂的OCR结果转换为结构化数据
   - 处理各种边缘情况和字段格式
   - 支持不同类型发票的通用格式

3. **异常处理**：
   - 处理文件保存、API调用、数据解析等异常
   - 对识别失败的图片保存副本便于后续分析

4. **图片文件管理**：
   - 临时文件使用`temp_`前缀
   - 最终文件名使用发票代码+发票号码
   - 处理文件复制、移动和删除

## 常见问题与解决方案

1. **无法识别发票代码或号码**：
   - 可能是图片质量问题，尝试提高图片清晰度
   - 对于普票，系统尝试从发票号码中提取发票代码
   - 查看logs目录下的日志文件获取详细错误信息

2. **OCR API调用失败**：
   - 检查API密钥是否正确设置
   - 查看网络连接是否正常
   - 检查API调用限额是否超限

3. **重复发票处理**：
   - 系统自动检查发票代码和号码是否已存在
   - 对于重复发票，返回已存在的发票ID而不是错误
   - 删除重复上传的临时文件

## 扩展与改进建议

1. **支持更多发票类型**：
   - 增加对电子普通发票的支持
   - 增加对卷式发票的支持
   - 增加对通行费发票的支持

2. **OCR引擎优化**：
   - 支持多种OCR服务提供商（百度、阿里云等）
   - 添加本地OCR支持，减少API依赖
   - 对OCR结果进行纠错和验证

3. **性能优化**：
   - 添加图片预处理以提高识别率
   - 实现批量处理功能
   - 添加识别缓存减少重复调用

4. **QR码处理**：
   - 增强QR码识别功能
   - 从QR码中提取并验证发票信息
   - 利用QR码数据自动填充缺失字段

## 开发与测试

1. **本地测试OCR API**：
   ```bash
   python3 core/ocr_api.py <图片路径>
   ```

2. **测试发票格式化**：
   ```bash
   python3 core/invoice_formatter.py <JSON文件路径>
   ```

3. **调试提示**：
   - 调整日志级别获取更多调试信息
   - 检查`app/static/uploads`目录中的失败图片副本
   - 使用模拟数据测试格式化功能 
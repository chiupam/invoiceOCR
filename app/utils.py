#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

# 导入核心功能模块
from core.ocr_api import OCRClient
from core.invoice_formatter import InvoiceFormatter
from core.invoice_export import InvoiceExporter

# 导入数据库模型
from .models import db, Invoice, InvoiceItem, Project


def allowed_file(filename):
    """检查文件扩展名是否允许上传"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_uploaded_file(file):
    """
    保存上传的文件
    
    参数:
        file: 上传的文件对象
        
    返回:
        保存后的文件路径
    """
    if file and allowed_file(file.filename):
        # 生成安全的文件名
        filename = secure_filename(file.filename)
        # 添加时间戳和随机字符串，避免文件名冲突
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = uuid.uuid4().hex[:8]
        # 文件名格式: 原文件名_时间戳_随机字符串.扩展名
        filename = f"{os.path.splitext(filename)[0]}_{timestamp}_{random_str}{os.path.splitext(filename)[1]}"
        
        # 保存文件
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 返回相对路径（用于数据库存储）- 只返回文件名
        return filename
    
    return None


def process_invoice_image(image_path, project_id=None):
    """
    处理发票图片，识别并保存发票数据
    
    参数:
        image_path: 图片在服务器上的完整路径
        project_id: 项目ID，默认为None
        
    返回:
        包含success标志和结果的字典
    """
    # 创建OCR API客户端
    ocr_api = OCRClient()
    
    try:
        # 调用OCR API识别发票
        response_json = ocr_api.recognize_vat_invoice(image_path=image_path)
        
        # 格式化发票数据
        formatted_data = InvoiceFormatter.format_invoice_data(json_string=response_json)
        
        # 提取关键信息用于返回
        invoice_data = {
            'invoice_code': formatted_data.get('基本信息', {}).get('发票代码', ''),
            'invoice_number': formatted_data.get('基本信息', {}).get('发票号码', ''),
            'invoice_type': formatted_data.get('基本信息', {}).get('发票类型', ''),
            'seller_name': formatted_data.get('销售方信息', {}).get('名称', ''),
            'seller_tax_id': formatted_data.get('销售方信息', {}).get('识别号', ''),
            'seller_address': formatted_data.get('销售方信息', {}).get('地址电话', ''),
            'seller_bank_info': formatted_data.get('销售方信息', {}).get('开户行及账号', ''),
            'buyer_name': formatted_data.get('购买方信息', {}).get('名称', ''),
            'buyer_tax_id': formatted_data.get('购买方信息', {}).get('识别号', ''),
            'buyer_address': formatted_data.get('购买方信息', {}).get('地址电话', ''),
            'buyer_bank_info': formatted_data.get('购买方信息', {}).get('开户行及账号', ''),
            'total_amount': formatted_data.get('金额信息', {}).get('合计金额', ''),
            'total_tax': formatted_data.get('金额信息', {}).get('合计税额', ''),
            'amount_in_words': formatted_data.get('金额信息', {}).get('价税合计(大写)', ''),
            'amount_in_figures': formatted_data.get('金额信息', {}).get('价税合计(小写)', ''),
            'invoice_date': None,
            'json_data': formatted_data  # 保存完整的格式化数据
        }
        
        # 处理日期
        invoice_date_raw = formatted_data.get('基本信息', {}).get('开票日期', '')
        invoice_date_std = formatted_data.get('基本信息', {}).get('开票日期标准格式', '')
        if invoice_date_std:
            try:
                invoice_data['invoice_date'] = datetime.strptime(invoice_date_std, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # 检查是否已存在相同代码和号码的发票
        invoice_code = invoice_data.get('invoice_code')
        invoice_number = invoice_data.get('invoice_number')
        
        from app.models import Invoice, InvoiceItem, db
        
        if invoice_code and invoice_number:
            existing_invoice = Invoice.query.filter_by(
                invoice_code=invoice_code,
                invoice_number=invoice_number
            ).first()
            
            if existing_invoice:
                return {
                    'success': True,
                    'message': f'发票已存在 (ID: {existing_invoice.id})',
                    'invoice_id': existing_invoice.id
                }
            
            # 使用发票代码和号码创建新的文件名
            filename = secure_filename(os.path.basename(image_path))
            new_filename = f"{invoice_code}{invoice_number}{os.path.splitext(filename)[1]}"
        else:
            # 如果没有识别出代码和号码，使用原文件名
            new_filename = os.path.basename(image_path)
        
        # 最终文件路径
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        final_file_path = os.path.join(upload_folder, new_filename)
        
        # 移动文件
        import shutil
        shutil.copy2(image_path, final_file_path)
        
        # 删除原始临时文件
        try:
            os.remove(image_path)
        except:
            current_app.logger.warning(f"无法删除临时文件: {image_path}")
        
        # 创建新发票记录
        invoice = Invoice(
            invoice_code=invoice_data.get('invoice_code', ''),
            invoice_number=invoice_data.get('invoice_number', ''),
            invoice_type=invoice_data.get('invoice_type', ''),
            invoice_date=invoice_data.get('invoice_date'),
            seller_name=invoice_data.get('seller_name', ''),
            seller_tax_id=invoice_data.get('seller_tax_id', ''),
            seller_address=invoice_data.get('seller_address', ''),
            seller_bank_info=invoice_data.get('seller_bank_info', ''),
            buyer_name=invoice_data.get('buyer_name', ''),
            buyer_tax_id=invoice_data.get('buyer_tax_id', ''),
            buyer_address=invoice_data.get('buyer_address', ''),
            buyer_bank_info=invoice_data.get('buyer_bank_info', ''),
            total_amount=invoice_data.get('total_amount', ''),
            total_tax=invoice_data.get('total_tax', ''),
            amount_in_words=invoice_data.get('amount_in_words', ''),
            amount_in_figures=invoice_data.get('amount_in_figures', ''),
            image_path=new_filename,  # 直接使用文件名，不要添加uploads/前缀
            project_id=project_id
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        # 创建发票项目关联
        if 'json_data' in invoice_data and invoice_data['json_data']:
            formatted_data = invoice_data['json_data']
            # 处理商品项目
            items_data = formatted_data.get('商品信息', [])
            for item_data in items_data:
                item = InvoiceItem.from_item_data(invoice.id, item_data)
                db.session.add(item)
            
            # 保存完整JSON数据
            invoice.json_data = json.dumps(formatted_data, ensure_ascii=False)
            db.session.commit()
        
        return {
            'success': True,
            'message': '发票识别并保存成功',
            'invoice_id': invoice.id
        }
        
    except Exception as e:
        current_app.logger.error(f"处理发票图片时出错: {str(e)}")
        return {
            'success': False,
            'message': f'处理发票时出错: {str(e)}'
        }


def get_invoice_statistics(invoices=None):
    """获取发票统计数据"""
    from app.models import Invoice
    from datetime import datetime
    
    # 如果没有传入发票列表，则查询所有发票
    if invoices is None:
        invoices = Invoice.query.all()
    
    # 总发票数
    invoice_count = len(invoices)
    
    # 总金额 - 使用价税合计(小写)而不是合计金额
    total_amount = 0
    for invoice in invoices:
        if invoice.amount_in_figures:
            try:
                # 去除¥符号和空格，转为浮点数
                amount = float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip())
                total_amount += amount
            except ValueError:
                # 忽略无法转换的金额
                pass
    
    # 获取当前年月
    current_month = datetime.now().strftime('%Y-%m')
    
    # 当月发票数量
    current_month_count = 0
    current_month_amount = 0
    
    # 按月份统计发票数量
    monthly_data = {}
    for invoice in invoices:
        if invoice.invoice_date:
            month_key = invoice.invoice_date.strftime('%Y-%m')
            
            # 统计当月发票
            if month_key == current_month:
                current_month_count += 1
                # 累加当月金额 - 使用价税合计
                if invoice.amount_in_figures:
                    try:
                        amount = float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip())
                        current_month_amount += amount
                    except ValueError:
                        pass
            
            # 所有月份数据
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'count': 0,
                    'amount': 0
                }
            monthly_data[month_key]['count'] += 1
            
            # 累加金额
            amount = 0
            if invoice.amount_in_figures:
                try:
                    amount = float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip())
                except ValueError:
                    pass
            monthly_data[month_key]['amount'] += amount
    
    # 按月份排序
    sorted_months = sorted(monthly_data.keys())
    
    # 计算发票类型分布
    type_data = {}
    for invoice in invoices:
        if invoice.invoice_type:
            if invoice.invoice_type not in type_data:
                type_data[invoice.invoice_type] = 0
            type_data[invoice.invoice_type] += 1
    
    # 返回统计结果
    return {
        'invoice_count': invoice_count,
        'total_amount': "{:,.2f}".format(total_amount),
        'current_month': {
            'month': current_month,
            'count': current_month_count,
            'amount': "{:,.2f}".format(current_month_amount)
        },
        'monthly_data': {
            'labels': sorted_months,
            'counts': [monthly_data[month]['count'] for month in sorted_months],
            'amounts': [monthly_data[month]['amount'] for month in sorted_months]
        },
        'type_data': {
            'labels': list(type_data.keys()),
            'counts': list(type_data.values())
        }
    }


def export_invoice(invoice_id, format, auto_delete=False):
    """
    导出发票数据为指定格式
    
    参数:
        invoice_id: 发票ID
        format: 导出格式，'csv'或'excel'
        auto_delete: 是否在返回路径后将文件标记为待删除（默认False）
        
    返回:
        导出文件的路径
    """
    # 查询发票对象
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # 获取完整的发票数据
    invoice_data = json.loads(invoice.json_data)
    
    # 导出为指定格式
    if format == 'csv':
        file_path = InvoiceExporter.export_to_csv(invoice_data)
    elif format == 'excel':
        file_path = InvoiceExporter.export_to_excel(invoice_data)
    else:
        return None
        
    # 如果开启自动删除，在session中记录该文件路径用于后续删除
    if auto_delete and file_path:
        if 'files_to_delete' not in current_app.config:
            current_app.config['files_to_delete'] = []
        current_app.config['files_to_delete'].append(file_path)
    
    return file_path


def export_project(project_id, auto_delete=False):
    """
    导出项目数据为Excel格式
    
    参数:
        project_id: 项目ID
        auto_delete: 是否在返回路径后将文件标记为待删除（默认False）
        
    返回:
        导出文件的路径
    """
    from core.invoice_export import export_project_to_excel
    
    # 查询项目对象
    project = Project.query.get_or_404(project_id)
    
    # 查询项目下的所有发票
    invoices = Invoice.query.filter_by(project_id=project_id).all()
    
    # 为每个发票查询其明细项
    for invoice in invoices:
        # 查询发票明细项
        items = InvoiceItem.query.filter_by(invoice_id=invoice.id).all()
        # 将明细项附加到发票对象
        invoice.items = items
        
        # 尝试解析JSON数据以获取更多详情
        if invoice.json_data:
            try:
                invoice.formatted_data = json.loads(invoice.json_data)
            except:
                invoice.formatted_data = None
    
    # 整理项目数据
    project_data = {
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at,
        'updated_at': project.updated_at
    }
    
    # 导出为Excel格式
    file_path = export_project_to_excel(project_data, invoices)
    
    # 如果开启自动删除，在session中记录该文件路径用于后续删除
    if auto_delete and file_path:
        if 'files_to_delete' not in current_app.config:
            current_app.config['files_to_delete'] = []
        current_app.config['files_to_delete'].append(file_path)
    
    return file_path


def delete_invoice(invoice_id):
    """
    删除发票及其相关数据
    
    参数:
        invoice_id: 发票ID
        
    返回:
        是否成功删除
    """
    try:
        # 查询发票
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # 删除相关联的发票明细项
        InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
        
        # 删除发票图片文件
        if invoice.image_path:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], invoice.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # 删除发票记录
        db.session.delete(invoice)
        db.session.commit()
        
        return True
    except Exception as e:
        current_app.logger.error(f"删除发票时出错: {str(e)}")
        db.session.rollback()
        return False


def update_invoice_from_json(invoice_id):
    """
    从发票的JSON数据中更新发票记录的各个字段
    
    参数:
        invoice_id: 发票ID
        
    返回:
        是否成功更新
    """
    try:
        # 查询发票
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # 如果发票没有JSON数据，则无法更新
        if not invoice.json_data:
            return False
            
        # 解析JSON数据
        formatted_data = json.loads(invoice.json_data)
        
        # 提取各部分数据
        basic_info = formatted_data.get('基本信息', {})
        seller_info = formatted_data.get('销售方信息', {})
        buyer_info = formatted_data.get('购买方信息', {})
        amount_info = formatted_data.get('金额信息', {})
        other_info = formatted_data.get('其他信息', {})
        
        # 更新发票基本信息
        invoice.invoice_type = basic_info.get('发票类型', invoice.invoice_type)
        invoice.invoice_code = basic_info.get('发票代码', invoice.invoice_code)
        invoice.invoice_number = basic_info.get('发票号码', invoice.invoice_number)
        invoice.check_code = basic_info.get('校验码', invoice.check_code)
        invoice.machine_number = basic_info.get('机器编号', invoice.machine_number)
        
        # 处理日期
        invoice_date_std = basic_info.get('开票日期标准格式', '')
        if invoice_date_std:
            try:
                invoice.invoice_date = datetime.strptime(invoice_date_std, '%Y-%m-%d').date()
            except ValueError:
                pass
        invoice.invoice_date_raw = basic_info.get('开票日期', invoice.invoice_date_raw)
        
        # 更新销售方信息
        invoice.seller_name = seller_info.get('名称', invoice.seller_name)
        invoice.seller_tax_id = seller_info.get('识别号', invoice.seller_tax_id)
        invoice.seller_address = seller_info.get('地址电话', invoice.seller_address)
        invoice.seller_bank_info = seller_info.get('开户行及账号', invoice.seller_bank_info)
        
        # 更新购买方信息
        invoice.buyer_name = buyer_info.get('名称', invoice.buyer_name)
        invoice.buyer_tax_id = buyer_info.get('识别号', invoice.buyer_tax_id)
        invoice.buyer_address = buyer_info.get('地址电话', invoice.buyer_address)
        invoice.buyer_bank_info = buyer_info.get('开户行及账号', invoice.buyer_bank_info)
        
        # 更新金额信息
        invoice.total_amount = amount_info.get('合计金额', invoice.total_amount)
        invoice.total_tax = amount_info.get('合计税额', invoice.total_tax)
        invoice.amount_in_words = amount_info.get('价税合计(大写)', invoice.amount_in_words)
        invoice.amount_in_figures = amount_info.get('价税合计(小写)', invoice.amount_in_figures)
        
        # 更新其他信息
        invoice.remarks = other_info.get('备注', invoice.remarks)
        invoice.payee = other_info.get('收款人', invoice.payee)
        invoice.reviewer = other_info.get('复核', invoice.reviewer)
        invoice.issuer = other_info.get('开票人', invoice.issuer)
        
        # 提交更新
        db.session.commit()
        
        # 更新发票明细项
        items_data = formatted_data.get('商品信息', [])
        
        # 检查是否存在直接的商品数组格式
        if not items_data and isinstance(formatted_data.get('Response', {}).get('Items', []), list):
            items_data = formatted_data.get('Response', {}).get('Items', [])
        
        # 先删除原有的明细项
        InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
        
        # 添加新的明细项
        for item_data in items_data:
            item = InvoiceItem.from_item_data(invoice.id, item_data)
            db.session.add(item)
            
        db.session.commit()
        
        return True
    except Exception as e:
        current_app.logger.error(f"从JSON更新发票时出错: {str(e)}")
        db.session.rollback()
        return False


def update_all_invoices_from_json():
    """
    从JSON数据更新所有发票记录
    
    返回:
        成功更新的发票数量
    """
    # 查询所有有JSON数据的发票
    invoices = Invoice.query.filter(Invoice.json_data.isnot(None)).all()
    
    success_count = 0
    for invoice in invoices:
        if update_invoice_from_json(invoice.id):
            success_count += 1
    
    return success_count


def cleanup_exported_files():
    """
    清理已导出的临时文件
    
    返回:
        删除的文件数量
    """
    deleted_count = 0
    
    # 获取要删除的文件列表
    files_to_delete = current_app.config.get('files_to_delete', [])
    
    for file_path in files_to_delete[:]:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
                files_to_delete.remove(file_path)
        except Exception as e:
            current_app.logger.error(f"删除导出文件时出错: {str(e)}")
    
    # 更新文件列表
    current_app.config['files_to_delete'] = files_to_delete
    
    return deleted_count


def cleanup_old_exported_files(days=7):
    """
    清理output目录中超过指定天数的过期导出文件
    
    参数:
        days: 文件保留天数，默认7天
        
    返回:
        删除的文件数量
    """
    output_dir = current_app.config['OUTPUT_DIR']
    deleted_count = 0
    now = datetime.now()
    
    try:
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            
            # 跳过目录
            if not os.path.isfile(file_path):
                continue
                
            # 获取文件修改时间
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # 计算文件存在的天数
            file_age_days = (now - file_mtime).days
            
            # 如果文件超过指定天数，则删除
            if file_age_days > days:
                os.remove(file_path)
                deleted_count += 1
                
    except Exception as e:
        current_app.logger.error(f"清理过期导出文件时出错: {str(e)}")
    
    return deleted_count 
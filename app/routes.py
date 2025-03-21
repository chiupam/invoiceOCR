#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file, session, abort
from werkzeug.utils import secure_filename

from .models import db, Invoice, InvoiceItem, Project, Settings
from .utils import save_uploaded_file, process_invoice_image, get_invoice_statistics, export_invoice, delete_invoice, export_project, update_invoice_from_json, update_all_invoices_from_json

# 创建蓝图
main = Blueprint('main', __name__)

# 允许的文件类型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """检查文件是否为允许的类型"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 添加检查系统是否设置完成的函数
def check_system_setup():
    """检查系统是否已设置（腾讯云API密钥）"""
    tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID')
    tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY')
    return bool(tencent_secret_id and tencent_secret_key)

@main.route('/')
def index():
    """首页 - 发票列表"""
    # 检查系统是否已设置
    if not check_system_setup():
        flash('请先完成系统设置', 'warning')
        return redirect(url_for('settings'))
    
    # 获取筛选参数
    project_id = request.args.get('project_id', type=int)
    
    # 获取排序参数
    sort_by = request.args.get('sort_by', 'invoice_date')
    order = request.args.get('order', 'desc')
    
    # 查询发票列表
    query = Invoice.query
    
    # 应用项目筛选
    current_project = None
    if project_id is not None:
        if project_id == 0:  # 0表示未分类
            query = query.filter(Invoice.project_id.is_(None))
        else:
            query = query.filter_by(project_id=project_id)
            # 获取当前项目信息
            current_project = Project.query.get_or_404(project_id)
    
    # 应用排序
    if sort_by == 'invoice_date':
        if order == 'asc':
            query = query.order_by(Invoice.invoice_date.asc())
        else:
            query = query.order_by(Invoice.invoice_date.desc())
    elif sort_by == 'amount':
        # 以金额排序，这里简单实现，可能不太精确
        if order == 'asc':
            query = query.order_by(Invoice.amount_in_figures.asc())
        else:
            query = query.order_by(Invoice.amount_in_figures.desc())
    elif sort_by == 'created_at':
        if order == 'asc':
            query = query.order_by(Invoice.created_at.asc())
        else:
            query = query.order_by(Invoice.created_at.desc())
    
    # 执行查询
    invoices = query.all()
    
    # 查询项目列表
    projects = Project.query.order_by(Project.name).all()
    
    # 查询每个发票的项目数量
    invoice_items_count = {}
    for invoice in invoices:
        items_count = InvoiceItem.query.filter_by(invoice_id=invoice.id).count()
        invoice_items_count[invoice.id] = items_count
    
    # 获取统计信息 - 传入筛选后的发票列表而不是全部发票
    stats = get_invoice_statistics(invoices)
    
    # 确保stats中有正确的结构
    if 'monthly_data' not in stats:
        stats['monthly_data'] = {'months': [], 'counts': []}
    
    # 确保有发票类型分布数据
    if 'type_data' not in stats:
        # 计算发票类型分布
        type_data = {}
        for invoice in invoices:
            if invoice.invoice_type:
                if invoice.invoice_type not in type_data:
                    type_data[invoice.invoice_type] = 0
                type_data[invoice.invoice_type] += 1
        
        stats['type_data'] = {
            'labels': list(type_data.keys()),
            'counts': list(type_data.values())
        }
    
    return render_template('index.html', 
                           invoices=invoices,
                           projects=projects,
                           current_project_id=project_id,
                           current_project=current_project,
                           invoice_items_count=invoice_items_count,
                           stats=stats,
                           sort_by=sort_by,
                           order=order)


@main.route('/upload', methods=['GET', 'POST'])
def upload():
    """上传发票页面"""
    # 获取项目列表
    projects = Project.query.order_by(Project.name).all()
    
    # 获取URL参数中的project_id
    default_project_id = request.args.get('project_id', None)
    if default_project_id:
        try:
            default_project_id = int(default_project_id)
            # 保存到会话，作为下次默认值
            session['last_project_id'] = default_project_id
        except (ValueError, TypeError):
            default_project_id = None
    
    # 如果URL没有指定项目ID，则尝试使用上次选择的项目ID
    if default_project_id is None and 'last_project_id' in session:
        default_project_id = session['last_project_id']
        try:
            default_project_id = int(default_project_id)
        except (ValueError, TypeError):
            default_project_id = None
    
    if request.method == 'POST':
        # 检查是否有文件上传
        if 'invoice_file' not in request.files:
            flash('没有选择文件')
            return redirect(request.url)
        
        file = request.files['invoice_file']
        
        # 检查文件名是否为空
        if file.filename == '':
            flash('没有选择文件')
            return redirect(request.url)
        
        # 检查文件类型
        if file and allowed_file(file.filename):
            # 安全处理文件名
            filename = secure_filename(file.filename)
            
            # 创建文件保存目录
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # 先保存临时文件进行识别
            temp_file_path = os.path.join(upload_folder, "temp_" + filename)
            file.save(temp_file_path)
            
            # 获取项目ID (强制转换为整数，如果为空则为None)
            project_id = request.form.get('project_id')
            if project_id:
                try:
                    project_id = int(project_id)
                    if project_id <= 0:  # 0或负数视为未分类
                        project_id = None
                    # 记住选择的项目ID
                    session['last_project_id'] = project_id
                except (ValueError, TypeError):
                    project_id = None
            else:
                project_id = None  # 明确设置为None
            
            # 处理发票图片并识别数据
            invoice_data = process_invoice_image(temp_file_path)
            
            # 检查是否识别成功
            if not invoice_data:
                os.remove(temp_file_path)  # 删除临时文件
                flash('发票识别失败，请检查图片质量或发票类型')
                return redirect(request.url)
                
            # 检查是否已存在相同代码和号码的发票
            invoice_code = invoice_data.get('invoice_code')
            invoice_number = invoice_data.get('invoice_number')
            
            if invoice_code and invoice_number:
                existing_invoice = Invoice.query.filter_by(
                    invoice_code=invoice_code,
                    invoice_number=invoice_number
                ).first()
                
                if existing_invoice:
                    os.remove(temp_file_path)  # 删除临时文件
                    flash(f'该发票已存在 (ID: {existing_invoice.combined_id})')
                    return redirect(url_for('main.invoice_detail', invoice_id=existing_invoice.id))
                
                # 使用发票代码和号码创建新的文件名
                new_filename = f"{invoice_code}{invoice_number}{os.path.splitext(filename)[1]}"
            else:
                # 如果没有识别出代码和号码，使用时间戳和随机字符串
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                random_str = os.urandom(4).hex()
                new_filename = f"invoice_{timestamp}_{random_str}{os.path.splitext(filename)[1]}"
            
            # 最终文件路径
            final_file_path = os.path.join(upload_folder, new_filename)
            
            # 重命名文件
            os.rename(temp_file_path, final_file_path)
            
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
                project_id=project_id  # 确保正确设置项目ID
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
            
            flash('发票上传和识别成功')
            
            # 重定向到发票详情页以便编辑识别结果
            return redirect(url_for('main.invoice_detail', invoice_id=invoice.id))
        else:
            flash('不支持的文件类型')
            return redirect(request.url)
    
    return render_template('upload.html', 
                          projects=projects, 
                          default_project_id=default_project_id,
                          current_project_id=default_project_id)


@main.route('/invoice/<int:invoice_id>')
def invoice_detail(invoice_id):
    """发票详情页"""
    # 查询发票数据
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # 尝试从JSON数据更新发票信息
    if invoice.json_data and (not invoice.seller_tax_id or not invoice.total_tax):
        update_invoice_from_json(invoice_id)
    
    # 查询发票商品项目
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    # 提取JSON数据（如果有）
    json_data = None
    if invoice.json_data:
        try:
            json_data = json.loads(invoice.json_data)
        except:
            pass
    
    # 获取项目列表，用于侧边栏
    projects = Project.query.order_by(Project.name).all()
    
    # 获取当前项目ID，用于侧边栏高亮
    current_project_id = invoice.project_id
    
    return render_template('invoice_detail.html', 
                          invoice=invoice, 
                          items=items,
                          json_data=json_data,
                          projects=projects,
                          current_project_id=current_project_id)


@main.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
def invoice_edit(invoice_id):
    """编辑发票信息"""
    # 查询发票数据
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # 获取项目列表
    projects = Project.query.order_by(Project.name).all()
    
    # 获取当前项目ID，用于侧边栏高亮
    current_project_id = invoice.project_id
    
    if request.method == 'POST':
        # 更新发票基本信息
        invoice.invoice_type = request.form.get('invoice_type', '')
        invoice.invoice_code = request.form.get('invoice_code', '')
        invoice.invoice_number = request.form.get('invoice_number', '')
        
        # 处理日期
        invoice_date_str = request.form.get('invoice_date', '')
        if invoice_date_str:
            try:
                invoice.invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
                invoice.invoice_date_raw = invoice_date_str
            except ValueError:
                invoice.invoice_date_raw = invoice_date_str
        
        # 更新其他信息...
        invoice.seller_name = request.form.get('seller_name', '')
        invoice.seller_tax_id = request.form.get('seller_tax_id', '')
        invoice.buyer_name = request.form.get('buyer_name', '')
        invoice.buyer_tax_id = request.form.get('buyer_tax_id', '')
        invoice.total_amount = request.form.get('total_amount', '')
        invoice.total_tax = request.form.get('total_tax', '')
        invoice.amount_in_figures = request.form.get('amount_in_figures', '')
        
        # 更新项目关联
        project_id = request.form.get('project_id', type=int)
        invoice.project_id = project_id
        
        # 保存到数据库
        db.session.commit()
        
        flash('发票信息更新成功')
        return redirect(url_for('main.invoice_detail', invoice_id=invoice.id))
    
    return render_template('invoice_edit.html', 
                          invoice=invoice, 
                          projects=projects,
                          current_project_id=current_project_id)


@main.route('/invoice/<int:invoice_id>/delete', methods=['GET', 'POST'])
def invoice_delete(invoice_id):
    """删除发票"""
    # 查询发票数据
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # 获取项目列表，用于侧边栏
    projects = Project.query.order_by(Project.name).all()
    
    # 获取当前项目ID，用于侧边栏高亮
    current_project_id = invoice.project_id
    
    # 如果是GET请求，显示确认页面
    if request.method == 'GET':
        return render_template('confirm_delete.html', 
                              invoice=invoice,
                              projects=projects,
                              current_project_id=current_project_id)
    
    # 先删除关联的商品项目
    InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
    
    # 删除发票
    db.session.delete(invoice)
    db.session.commit()
    
    flash('发票已删除')
    return redirect(url_for('main.index'))


@main.route('/invoice/<int:invoice_id>/export/<format>')
def invoice_export(invoice_id, format):
    """导出发票数据"""
    try:
        # 调用导出函数
        file_path = export_invoice(invoice_id, format, auto_delete=True)
        
        if not file_path or not os.path.exists(file_path):
            flash('导出失败: 文件生成错误', 'danger')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))
            
        # 从文件路径获取文件名
        filename = os.path.basename(file_path)
        
        # 发送文件给用户下载
        return send_file(file_path, 
                         as_attachment=True,
                         download_name=filename,
                         mimetype='application/octet-stream')
    except Exception as e:
        flash(f'导出失败: {str(e)}', 'danger')
        return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))


@main.route('/api/statistics')
def api_statistics():
    """获取发票统计数据（JSON格式）"""
    # 获取所有发票
    invoices = Invoice.query.all()
    
    # 总发票数
    invoice_count = len(invoices)
    
    # 总金额
    total_amount = sum(float(invoice.total_amount.replace('¥', '').strip()) if invoice.total_amount else 0 for invoice in invoices)
    
    # 月度统计数据
    monthly_data = {}
    for invoice in invoices:
        if invoice.invoice_date:
            month_key = invoice.invoice_date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'count': 0,
                    'amount': 0
                }
            monthly_data[month_key]['count'] += 1
            
            # 累加金额
            amount = 0
            if invoice.total_amount:
                try:
                    amount = float(invoice.total_amount.replace('¥', '').strip())
                except ValueError:
                    pass
            monthly_data[month_key]['amount'] += amount
    
    # 按月份排序
    sorted_months = sorted(monthly_data.keys())
    
    # 发票类型分布
    type_data = {}
    for invoice in invoices:
        if invoice.invoice_type:
            if invoice.invoice_type not in type_data:
                type_data[invoice.invoice_type] = 0
            type_data[invoice.invoice_type] += 1
    
    # 构建最终数据结构
    formatted_data = {
        'invoice_count': invoice_count,
        'total_amount': "{:.2f}".format(total_amount),
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
    
    return jsonify(formatted_data)


# 更新项目列表页面
@main.route('/projects')
def project_list():
    """项目列表页面"""
    projects = Project.query.order_by(Project.name).all()
    
    # 获取每个项目的发票数量
    project_stats = {}
    for project in projects:
        invoice_count = Invoice.query.filter_by(project_id=project.id).count()
        project_stats[project.id] = {
            'invoice_count': invoice_count
        }
    
    # 未分类发票数量
    unclassified_count = Invoice.query.filter_by(project_id=None).count()
    
    return render_template('project_list.html', 
                           projects=projects, 
                           project_stats=project_stats,
                           unclassified_count=unclassified_count,
                           current_project_id=None)  # 在项目列表页不高亮任何项目


@main.route('/projects/create', methods=['GET', 'POST'])
def project_create():
    """创建新项目"""
    # 获取所有项目，用于侧边栏
    projects = Project.query.order_by(Project.name).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('项目名称不能为空')
            return redirect(url_for('main.project_create'))
        
        # 创建新项目
        project = Project(name=name, description=description)
        db.session.add(project)
        db.session.commit()
        
        flash('项目创建成功')
        return redirect(url_for('main.project_list'))
    
    return render_template('project_form.html', 
                          title='创建新项目',
                          projects=projects,
                          current_project_id=None)


@main.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def project_edit(project_id):
    """编辑项目"""
    project = Project.query.get_or_404(project_id)
    
    # 获取所有项目，用于侧边栏
    projects = Project.query.order_by(Project.name).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('项目名称不能为空')
            return redirect(url_for('main.project_edit', project_id=project_id))
        
        # 更新项目信息
        project.name = name
        project.description = description
        db.session.commit()
        
        flash('项目更新成功')
        return redirect(url_for('main.project_list'))
    
    return render_template('project_form.html', 
                          title='编辑项目', 
                          project=project,
                          projects=projects,
                          current_project_id=project_id)

@main.route('/projects/<int:project_id>/delete', methods=['POST'])
def project_delete(project_id):
    """删除项目"""
    project = Project.query.get_or_404(project_id)
    
    # 处理关联的发票
    handle_invoices = request.form.get('handle_invoices', 'unclassify')
    
    if handle_invoices == 'unclassify':
        # 将关联的发票设为未分类
        Invoice.query.filter_by(project_id=project_id).update({Invoice.project_id: None})
    elif handle_invoices == 'delete':
        # 删除关联的发票
        invoices = Invoice.query.filter_by(project_id=project_id).all()
        for invoice in invoices:
            # 删除发票明细
            InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
            # 删除发票
            db.session.delete(invoice)
    
    # 删除项目
    db.session.delete(project)
    db.session.commit()
    
    flash('项目已删除')
    return redirect(url_for('main.project_list'))

@main.route('/project/<int:project_id>')
def project_detail(project_id):
    """项目详情页面"""
    project = Project.query.get_or_404(project_id)
    # 获取当前项目下的所有发票
    invoices = Invoice.query.filter_by(project_id=project_id).all()
    
    # 获取所有项目列表（用于侧边栏）
    projects = Project.query.order_by(Project.created_at.desc()).all()
    
    return render_template('project_detail.html',
                          title=f'项目: {project.name}',
                          project=project,
                          invoices=invoices,
                          projects=projects,
                          current_project_id=project_id)

@main.route('/project/<int:project_id>/export')
def project_export(project_id):
    """导出项目数据"""
    try:
        # 调用导出函数
        file_path = export_project(project_id, auto_delete=True)
        
        if not file_path or not os.path.exists(file_path):
            flash('导出失败: 文件生成错误', 'danger')
            return redirect(url_for('main.project_detail', project_id=project_id))
            
        # 从文件路径获取文件名
        filename = os.path.basename(file_path)
        
        # 发送文件给用户下载
        return send_file(file_path, 
                         as_attachment=True,
                         download_name=filename,
                         mimetype='application/octet-stream')
    except Exception as e:
        flash(f'导出失败: {str(e)}', 'danger')
        return redirect(url_for('main.project_detail', project_id=project_id))

@main.route('/api/update-all-invoices', methods=['POST'])
def update_all_invoices():
    """从JSON数据更新所有发票记录"""
    if request.method == 'POST':
        updated_count = update_all_invoices_from_json()
        return jsonify({
            'success': True,
            'message': f'成功更新了 {updated_count} 条发票记录',
            'updated_count': updated_count
        })
    return jsonify({'success': False, 'message': '请使用POST方法访问此接口'})

@main.route('/invoice/<int:invoice_id>/update-from-json')
def update_invoice_from_json(invoice_id):
    """从JSON数据更新单个发票记录"""
    from app.utils import update_invoice_from_json as update_func
    result = update_func(invoice_id)
    
    if result:
        flash('成功从JSON数据更新了发票信息', 'success')
    else:
        flash('未能从JSON数据更新发票信息', 'warning')
        
    return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))

@main.route('/api/cleanup-exported-files', methods=['POST'])
def cleanup_files():
    """清理已导出的文件"""
    if request.method == 'POST':
        from app.utils import cleanup_exported_files, cleanup_old_exported_files
        
        # 清理标记为待删除的文件
        deleted_count1 = cleanup_exported_files()
        
        # 清理过期文件(默认7天)
        deleted_count2 = cleanup_old_exported_files()
        
        return jsonify({
            'success': True,
            'message': f'成功清理了 {deleted_count1 + deleted_count2} 个文件',
            'deleted_count': deleted_count1 + deleted_count2
        })
        
    return jsonify({'success': False, 'message': '请使用POST方法访问此接口'})

# 设置页面
@main.route('/settings', methods=['GET', 'POST'])
def settings():
    """系统设置页面"""
    if request.method == 'POST':
        # 保存设置
        tencent_secret_id = request.form.get('tencent_secret_id', '').strip()
        tencent_secret_key = request.form.get('tencent_secret_key', '').strip()
        
        # 验证输入
        if not tencent_secret_id or not tencent_secret_key:
            flash('请填写所有必填字段', 'danger')
            return redirect(url_for('settings'))
        
        # 保存设置
        Settings.set_value('TENCENT_SECRET_ID', tencent_secret_id)
        Settings.set_value('TENCENT_SECRET_KEY', tencent_secret_key)
        
        flash('设置已保存', 'success')
        return redirect(url_for('index'))
    
    # 获取当前设置
    tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID', '')
    tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY', '')
    
    return render_template('settings.html', 
                           tencent_secret_id=tencent_secret_id,
                           tencent_secret_key=tencent_secret_key) 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file, session, abort
from werkzeug.utils import secure_filename
from sqlalchemy import desc, func
from decimal import Decimal
import re

from .models import db, Invoice, InvoiceItem, Project, Settings
from .utils import save_uploaded_file, process_invoice_image, get_invoice_statistics, export_invoice, delete_invoice, export_project

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
@main.route('/index')
def index():
    """发票首页"""
    # 获取URL参数
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示的发票数量
    
    # 获取排序参数
    sort_by = request.args.get('sort_by', 'invoice_date')
    order = request.args.get('order', 'desc')
    
    # 获取项目ID参数
    project_id = request.args.get('project_id', None)
    if project_id is not None:
        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            project_id = None
    
    # 获取搜索查询参数
    search_query = request.args.get('search', '')
    
    # 初始化查询对象
    query = Invoice.query
    
    # 按项目过滤
    current_project = None
    if project_id is not None:
        if project_id == 0:
            # 特殊情况：显示未分类发票
            query = query.filter(Invoice.project_id == None)
            current_project_id = 0
        else:
            # 查询特定项目ID
            query = query.filter_by(project_id=project_id)
            current_project = Project.query.get(project_id)
            current_project_id = project_id
    else:
        # 不筛选项目
        current_project_id = None
    
    # 应用搜索过滤
    if search_query:
        query = query.filter(Invoice.invoice_number.like(f'%{search_query}%'))
    
    # 应用排序
    if sort_by == 'invoice_date':
        if order == 'asc':
            query = query.order_by(Invoice.invoice_date.asc())
        else:
            query = query.order_by(Invoice.invoice_date.desc())
    elif sort_by == 'amount':
        # 查询所有发票，再根据金额进行排序
        all_invoices = query.all()
        # 将金额从字符串转换为Decimal以用于排序
        all_invoices.sort(
            key=lambda inv: Decimal(re.sub(r'[^\d.]', '', inv.amount_in_figures)) if inv.amount_in_figures and re.sub(r'[^\d.]', '', inv.amount_in_figures) else Decimal('0'), 
            reverse=(order == 'desc')
        )
        
        # 应用分页 - 手动分页
        total = len(all_invoices)
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        pagination_items = all_invoices[start:end]
        
        # 自定义分页对象
        class PaginationObj:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page  # 总页数
                self.prev_num = page - 1 if page > 1 else None
                self.next_num = page + 1 if page < self.pages else None
            
            def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if num <= left_edge or \
                       (num > self.page - left_current - 1 and \
                        num < self.page + right_current) or \
                       num > self.pages - right_edge:
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num
        
        # 创建分页对象
        pagination = PaginationObj(items=pagination_items, page=page, per_page=per_page, total=total)
        
        # 更新发票列表为分页后的结果
        invoices = pagination_items
        
        # 设置已排序标志，防止执行后面的查询
        already_sorted = True
    elif sort_by == 'items_count':
        # 查询所有发票，加载关联的项目数据
        all_invoices = query.all()
        
        # 根据每个发票的项目数量排序
        if order == 'asc':
            all_invoices.sort(key=lambda inv: len(inv.items))
        else:
            all_invoices.sort(key=lambda inv: len(inv.items), reverse=True)
        
        # 应用分页 - 手动分页
        total = len(all_invoices)
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        pagination_items = all_invoices[start:end]
        
        # 自定义分页对象
        class PaginationObj:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page  # 总页数
                self.prev_num = page - 1 if page > 1 else None
                self.next_num = page + 1 if page < self.pages else None
            
            def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if num <= left_edge or \
                       (num > self.page - left_current - 1 and \
                        num < self.page + right_current) or \
                       num > self.pages - right_edge:
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num
        
        # 创建分页对象
        pagination = PaginationObj(items=pagination_items, page=page, per_page=per_page, total=total)
        
        # 更新发票列表为分页后的结果
        invoices = pagination_items
        
        # 设置已排序标志，防止执行后面的查询
        already_sorted = True
    elif sort_by == 'invoice_number':
        if order == 'asc':
            query = query.order_by(Invoice.invoice_number.asc())
        else:
            query = query.order_by(Invoice.invoice_number.desc())
    elif sort_by == 'created_at':
        if order == 'asc':
            query = query.order_by(Invoice.created_at.asc())
        else:
            query = query.order_by(Invoice.created_at.desc())
    
    # 执行查询（如果没有按项目数量排序）
    if not locals().get('already_sorted', False):
        # 带分页的查询
        pagination = query.paginate(page=page, per_page=per_page)
        invoices = pagination.items
    
    # 获取项目列表（用于侧边栏）
    projects = Project.query.order_by(Project.name).all()
    
    # 获取统计数据
    # 根据当前过滤条件获取统计
    if project_id is not None:
        if project_id == 0:
            # 特殊情况：只统计未分类发票
            filtered_invoices = Invoice.query.filter(Invoice.project_id == None).all()
        else:
            # 查询特定项目ID的发票
            filtered_invoices = Invoice.query.filter_by(project_id=project_id).all()
    else:
        # 不筛选项目，统计所有发票
        filtered_invoices = Invoice.query.all()
        
    stats = get_invoice_statistics(filtered_invoices)
    
    return render_template('index.html', 
                          invoices=invoices,
                          pagination=pagination,
                          projects=projects, 
                          stats=stats,
                          current_project_id=current_project_id,
                          current_project=current_project,
                          sort_by=sort_by,
                          order=order,
                          search_query=search_query)


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
            print("POST请求没有找到invoice_file字段", request.files)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': '没有选择文件'})
            flash('没有选择文件')
            return redirect(request.url)
        
        file = request.files['invoice_file']
        print(f"收到文件上传: {file.filename}")
        
        # 检查文件名是否为空
        if file.filename == '':
            print("文件名为空")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': '没有选择文件'})
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
            
            # 获取项目ID
            project_id = request.form.get('project_id', None)
            if project_id == '':
                project_id = None
            
            # 处理发票文件
            result = process_invoice_image(temp_file_path, project_id=project_id)
            
            if not result.get('success'):
                # 不再删除临时文件，因为process_invoice_image已经处理过或保存为failed_副本
                
                # 检查是否为XHR请求（AJAX）
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                    return jsonify({
                        'success': False,
                        'message': f'发票识别失败: {result.get("message", "未知错误")}'
                    })
                
                flash(f'发票识别失败: {result.get("message", "未知错误")}')
                return redirect(request.url)
            
            # 检查是否为XHR请求（AJAX）
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                # 获取发票详细信息，添加发票代码和发票号码到响应中
                invoice_id = result.get('invoice_id')
                invoice = Invoice.query.get(invoice_id)
                
                response_data = {
                    'success': True,
                    'message': '发票上传和识别成功',
                    'invoice_id': invoice_id,
                    'invoice_code': invoice.invoice_code,
                    'invoice_number': invoice.invoice_number
                }
                print(f"返回JSON响应: {response_data}")
                return jsonify(response_data)
                
            # 重定向到发票详情页面
            flash('发票上传和识别成功')
            return redirect(url_for('main.invoice_detail', invoice_id=result.get('invoice_id')))
        else:
            error_message = '不支持的文件类型'
            
            # 检查是否为XHR请求（AJAX）
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                return jsonify({
                    'success': False,
                    'message': error_message
                })
            
            flash(error_message)
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
    
    # 查询发票商品项目
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    # 获取项目列表，用于侧边栏
    projects = Project.query.order_by(Project.name).all()
    
    # 获取当前项目ID，用于侧边栏高亮
    current_project_id = invoice.project_id
    
    # 获取来源页面URL，用于返回按钮
    referer = request.headers.get('Referer', '')
    back_url = url_for('main.index')
    
    # 如果来源页面包含index并且有分页等参数，保留这些参数
    if 'index' in referer and ('page=' in referer or 'project_id=' in referer or 'sort_by=' in referer):
        back_url = referer
    
    return render_template('invoice_detail.html', 
                          invoice=invoice, 
                          items=items,
                          projects=projects,
                          current_project_id=current_project_id,
                          back_url=back_url)


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
        
        # 处理发票明细项
        # 首先删除现有的明细项
        InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
        
        # 从表单中获取明细项数据
        form_data = request.form.to_dict(flat=False)
        items_count = 0
        
        # 计算有多少个明细项
        for key in form_data:
            if key.startswith('items[') and key.endswith('][name]'):
                items_count = max(items_count, int(key.split('[')[1].split(']')[0]) + 1)
        
        # 添加新的明细项
        for i in range(items_count):
            # 检查该索引的明细是否存在
            if f'items[{i}][name]' in form_data and form_data[f'items[{i}][name]'][0].strip():
                item = InvoiceItem(
                    invoice_id=invoice_id,
                    name=form_data.get(f'items[{i}][name]', [''])[0],
                    specification=form_data.get(f'items[{i}][specification]', [''])[0],
                    unit=form_data.get(f'items[{i}][unit]', [''])[0],
                    quantity=form_data.get(f'items[{i}][quantity]', [''])[0],
                    price=form_data.get(f'items[{i}][price]', [''])[0],
                    amount=form_data.get(f'items[{i}][amount]', [''])[0],
                    tax_rate=form_data.get(f'items[{i}][tax_rate]', [''])[0],
                    tax=form_data.get(f'items[{i}][tax]', [''])[0]
                )
                db.session.add(item)
                current_app.logger.info(f"为发票ID={invoice_id}添加了明细项：{item.name}")
        
        # 保存到数据库
        try:
            db.session.commit()
            flash('发票信息更新成功')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"更新发票时出错: {str(e)}")
            flash(f'保存失败: {str(e)}', 'danger')
    
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
    
    # 保存图片路径，以便后续删除
    image_path = invoice.image_path
    
    # 先删除关联的商品项目
    InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
    
    # 删除发票
    db.session.delete(invoice)
    db.session.commit()
    
    # 删除对应的图片文件
    if image_path:
        try:
            # 构建完整的文件路径
            full_path = os.path.join(current_app.root_path, 'static', 'uploads', image_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                current_app.logger.info(f"已删除发票图片：{full_path}")
            else:
                current_app.logger.warning(f"找不到要删除的图片：{full_path}")
        except Exception as e:
            current_app.logger.error(f"删除发票图片出错：{str(e)}")
    
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
    
    # 总金额 - 使用价税合计(小写)
    total_amount = sum(float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip()) 
                       if invoice.amount_in_figures else 0 
                       for invoice in invoices)
    
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
            if invoice.amount_in_figures:
                try:
                    amount = float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip())
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
        'total_amount': "{:,.2f}".format(total_amount),
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
def api_update_all_invoices():
    """从JSON数据更新所有发票（API接口）"""
    if request.method == 'POST':
        from app.utils import update_all_invoices_from_json
        
        result = update_all_invoices_from_json()
        if result:
            return jsonify({
                'success': True,
                'message': f'成功更新了 {result} 条发票记录',
                'updated_count': result
            })
        return jsonify({
            'success': False,
            'message': '没有需要更新的发票记录'
        })
    return jsonify({'success': False, 'message': '请使用POST方法访问此接口'})

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
            return redirect(url_for('main.settings'))
        
        # 保存设置
        Settings.set_value('TENCENT_SECRET_ID', tencent_secret_id)
        Settings.set_value('TENCENT_SECRET_KEY', tencent_secret_key)
        
        flash('设置已保存', 'success')
        return redirect(url_for('main.index'))
    
    # 获取当前设置
    tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID', '')
    tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY', '')
    
    return render_template('settings.html', 
                           tencent_secret_id=tencent_secret_id,
                           tencent_secret_key=tencent_secret_key)

@main.route('/quick_upload', methods=['POST'])
def quick_upload():
    """快速上传接口 - 用于拖放上传功能"""
    # 检查系统是否已设置
    if not check_system_setup():
        flash('请先完成系统设置', 'warning')
        return redirect(url_for('main.settings'))
    
    # 检查上传的文件
    if 'invoice_file' not in request.files:
        flash('未检测到文件', 'danger')
        return redirect(url_for('main.index'))
    
    file = request.files['invoice_file']
    if file.filename == '':
        flash('未选择文件', 'danger')
        return redirect(url_for('main.index'))
    
    if not allowed_file(file.filename):
        flash('不支持的文件类型', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # 保存上传的文件
        filename = save_uploaded_file(file)
        
        if not filename:
            flash('文件保存失败', 'danger')
            return redirect(url_for('main.index'))
            
        # 构建完整的文件路径
        saved_path = os.path.join(current_app.root_path, 'static', 'uploads', filename)
        
        # 获取项目ID
        project_id = request.form.get('project_id', None)
        if project_id == '':
            project_id = None
        
        # 处理发票文件
        result = process_invoice_image(saved_path, project_id=project_id)
        
        if result.get('success'):
            invoice_id = result.get('invoice_id')
            
            # 如果提供了项目ID，则更新发票记录
            if project_id:
                try:
                    project_id = int(project_id)
                    invoice = Invoice.query.get(invoice_id)
                    if invoice:
                        invoice.project_id = project_id
                        db.session.commit()
                except (ValueError, TypeError):
                    pass
                
            flash('发票识别成功', 'success')
            
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))
        else:
            # 识别失败，process_invoice_image已经尝试删除临时文件
            flash(f'发票识别失败: {result["message"]}', 'danger')
            return redirect(url_for('main.index'))
            
    except Exception as e:
        flash(f'处理过程中出错: {str(e)}', 'danger')
        return redirect(url_for('main.index'))

# 注释掉从JSON更新单个发票的路由，让这个功能对普通用户不可用
# @main.route('/invoice/<int:invoice_id>/update-from-json')
# def update_invoice_from_json(invoice_id):
#     """从JSON数据更新单个发票记录"""
#     from app.utils import update_invoice_from_json as update_func
#     result = update_func(invoice_id)
#     
#     if result:
#         flash('成功从JSON数据更新了发票信息', 'success')
#     else:
#         flash('未能从JSON数据更新发票信息', 'warning')
#         
#     return redirect(url_for('main.invoice_detail', invoice_id=invoice_id)) 

@main.route('/invoice/create', methods=['GET', 'POST'])
def invoice_create():
    """新建发票"""
    # 获取项目列表
    projects = Project.query.order_by(Project.name).all()
    
    # 设置当前日期作为默认开票日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        try:
            # 创建新发票对象
            invoice = Invoice()
            
            # 填充基本信息
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
            
            # 填充其他信息
            invoice.seller_name = request.form.get('seller_name', '')
            invoice.seller_tax_id = request.form.get('seller_tax_id', '')
            invoice.buyer_name = request.form.get('buyer_name', '')
            invoice.buyer_tax_id = request.form.get('buyer_tax_id', '')
            invoice.total_amount = request.form.get('total_amount', '')
            invoice.total_tax = request.form.get('total_tax', '')
            invoice.amount_in_figures = request.form.get('amount_in_figures', '')
            
            # 设置项目关联
            project_id = request.form.get('project_id', type=int)
            invoice.project_id = project_id
            
            # 重要：设置图片路径为None，确保后续不会出错
            invoice.image_path = None
            
            # 先保存发票以获取ID
            db.session.add(invoice)
            db.session.flush()  # 获取ID但不提交事务
            
            current_app.logger.info(f"创建新发票: ID={invoice.id}, 类型={invoice.invoice_type}, 号码={invoice.invoice_number}")
            
            # 从表单中获取明细项数据
            form_data = request.form.to_dict(flat=False)
            items_added = 0
            
            # 查找并添加明细项
            for key in form_data:
                if key.startswith('items[') and key.endswith('][name]'):
                    index = key[6:].split(']')[0]
                    name = form_data.get(f'items[{index}][name]', [''])[0].strip()
                    
                    # 如果名称为空，跳过此项
                    if not name:
                        continue
                    
                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        name=name,
                        specification=form_data.get(f'items[{index}][specification]', [''])[0],
                        unit=form_data.get(f'items[{index}][unit]', [''])[0],
                        quantity=form_data.get(f'items[{index}][quantity]', [''])[0],
                        price=form_data.get(f'items[{index}][price]', [''])[0],
                        amount=form_data.get(f'items[{index}][amount]', [''])[0],
                        tax_rate=form_data.get(f'items[{index}][tax_rate]', [''])[0],
                        tax=form_data.get(f'items[{index}][tax]', [''])[0]
                    )
                    db.session.add(item)
                    items_added += 1
                    current_app.logger.info(f"为新发票添加了明细项：{item.name}")
            
            # 提交事务
            db.session.commit()
            flash(f'新发票创建成功，添加了{items_added}个明细项')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"创建发票时出错: {str(e)}")
            flash(f'保存失败: {str(e)}', 'danger')
    
    return render_template('invoice_create.html', 
                          projects=projects,
                          today=today) 
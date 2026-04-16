import os
import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_required

from ..models import db, Invoice, InvoiceItem, Project
from ..utils import process_invoice_image, get_invoice_statistics, export_invoice, save_uploaded_file
from ..models import Settings as SettingsModel

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def register_invoice_routes(bp):

    @bp.route('/')
    @bp.route('/index')
    @login_required
    def index():
        page = request.args.get('page', 1, type=int)
        per_page = 10
        sort_by = request.args.get('sort_by', 'invoice_date')
        order = request.args.get('order', 'desc')
        project_id = request.args.get('project_id', None)
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (ValueError, TypeError):
                project_id = None
        search_query = request.args.get('search', '')

        query = Invoice.query

        current_project = None
        if project_id is not None:
            if project_id == 0:
                query = query.filter(Invoice.project_id == None)
                current_project_id = 0
            else:
                query = query.filter_by(project_id=project_id)
                current_project = Project.query.get(project_id)
                current_project_id = project_id
        else:
            current_project_id = None

        if search_query:
            query = query.filter(Invoice.invoice_number.like(f'%{search_query}%'))

        if sort_by == 'invoice_date':
            query = query.order_by(Invoice.invoice_date.asc() if order == 'asc' else Invoice.invoice_date.desc())
        elif sort_by == 'amount':
            query = query.order_by(Invoice.amount_decimal.asc().nulls_last() if order == 'asc' else Invoice.amount_decimal.desc().nulls_last())
        elif sort_by == 'items_count':
            items_count_subq = db.session.query(
                InvoiceItem.invoice_id,
                db.func.count(InvoiceItem.id).label('items_count')
            ).group_by(InvoiceItem.invoice_id).subquery()
            query = query.outerjoin(items_count_subq, Invoice.id == items_count_subq.c.invoice_id)
            query = query.order_by(items_count_subq.c.items_count.asc().nulls_last() if order == 'asc' else items_count_subq.c.items_count.desc().nulls_last())
        elif sort_by == 'invoice_number':
            query = query.order_by(Invoice.invoice_number.asc() if order == 'asc' else Invoice.invoice_number.desc())
        elif sort_by == 'created_at':
            query = query.order_by(Invoice.created_at.asc() if order == 'asc' else Invoice.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page)
        invoices = pagination.items
        projects = Project.query.order_by(Project.name).all()

        if project_id is not None:
            if project_id == 0:
                filtered_invoices = Invoice.query.filter(Invoice.project_id == None).all()
            else:
                filtered_invoices = Invoice.query.filter_by(project_id=project_id).all()
        else:
            filtered_invoices = Invoice.query.all()

        stats = get_invoice_statistics(filtered_invoices)

        api_configured = bool(SettingsModel.get_value('TENCENT_SECRET_ID') and SettingsModel.get_value('TENCENT_SECRET_KEY'))

        return render_template('index.html',
                               invoices=invoices,
                               pagination=pagination,
                               projects=projects,
                               stats=stats,
                               current_project_id=current_project_id,
                               current_project=current_project,
                               sort_by=sort_by,
                               order=order,
                               search_query=search_query,
                               api_configured=api_configured)

    @bp.route('/upload', methods=['GET', 'POST'])
    @login_required
    def upload():
        projects = Project.query.order_by(Project.name).all()
        default_project_id = request.args.get('project_id', None)
        if default_project_id:
            try:
                default_project_id = int(default_project_id)
                session['last_project_id'] = default_project_id
            except (ValueError, TypeError):
                default_project_id = None

        if default_project_id is None and 'last_project_id' in session:
            default_project_id = session['last_project_id']
            try:
                default_project_id = int(default_project_id)
            except (ValueError, TypeError):
                default_project_id = None

        if request.method == 'POST':
            if 'invoice_file' not in request.files:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                    return jsonify({'success': False, 'message': '没有选择文件'})
                flash('没有选择文件')
                return redirect(request.url)

            file = request.files['invoice_file']

            if file.filename == '':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                    return jsonify({'success': False, 'message': '没有选择文件'})
                flash('没有选择文件')
                return redirect(request.url)

            if file and allowed_file(file.filename):
                filename = save_uploaded_file(file)
                if not filename:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                        return jsonify({'success': False, 'message': '文件保存失败'})
                    flash('文件保存失败')
                    return redirect(request.url)

                saved_path = os.path.join(current_app.root_path, 'static', 'uploads', filename)

                project_id = request.form.get('project_id', None)
                if project_id == '':
                    project_id = None

                result = process_invoice_image(saved_path, project_id=project_id)

                if not result.get('success'):
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                        return jsonify({
                            'success': False,
                            'message': f'发票识别失败: {result.get("message", "未知错误")}'
                        })
                    flash(f'发票识别失败: {result.get("message", "未知错误")}')
                    return redirect(request.url)

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                    invoice_id = result.get('invoice_id')
                    invoice = Invoice.query.get(invoice_id)
                    response_data = {
                        'success': True,
                        'message': '发票上传和识别成功',
                        'invoice_id': invoice_id,
                        'invoice_code': invoice.invoice_code,
                        'invoice_number': invoice.invoice_number
                    }
                    return jsonify(response_data)

                flash('发票上传和识别成功')
                return redirect(url_for('main.invoice_detail', invoice_id=result.get('invoice_id')))
            else:
                error_message = '不支持的文件类型'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                    return jsonify({'success': False, 'message': error_message})
                flash(error_message)
                return redirect(request.url)

        return render_template('upload.html',
                               projects=projects,
                               default_project_id=default_project_id,
                               current_project_id=default_project_id)

    @bp.route('/invoice/<int:invoice_id>')
    @login_required
    def invoice_detail(invoice_id):
        invoice = Invoice.query.get_or_404(invoice_id)
        items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        projects = Project.query.order_by(Project.name).all()
        current_project_id = invoice.project_id
        referer = request.headers.get('Referer', '')
        back_url = url_for('main.index')
        if 'index' in referer and ('page=' in referer or 'project_id=' in referer or 'sort_by=' in referer):
            back_url = referer

        confidence_data = None
        if invoice.json_data:
            try:
                json_data = json.loads(invoice.json_data)
                confidence_data = json_data.get('置信度', None)
            except (json.JSONDecodeError, ValueError):
                pass

        return render_template('invoice_detail.html',
                               invoice=invoice,
                               items=items,
                               projects=projects,
                               current_project_id=current_project_id,
                               back_url=back_url,
                               confidence_data=confidence_data)

    @bp.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
    @login_required
    def invoice_edit(invoice_id):
        invoice = Invoice.query.get_or_404(invoice_id)
        projects = Project.query.order_by(Project.name).all()
        current_project_id = invoice.project_id

        if request.method == 'POST':
            invoice.invoice_type = request.form.get('invoice_type', '')
            invoice.invoice_code = request.form.get('invoice_code', '')
            invoice.invoice_number = request.form.get('invoice_number', '')

            invoice_date_str = request.form.get('invoice_date', '')
            if invoice_date_str:
                try:
                    invoice.invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
                    invoice.invoice_date_raw = invoice_date_str
                except ValueError:
                    invoice.invoice_date_raw = invoice_date_str

            invoice.seller_name = request.form.get('seller_name', '')
            invoice.seller_tax_id = request.form.get('seller_tax_id', '')
            invoice.buyer_name = request.form.get('buyer_name', '')
            invoice.buyer_tax_id = request.form.get('buyer_tax_id', '')
            invoice.total_amount = request.form.get('total_amount', '')
            invoice.total_tax = request.form.get('total_tax', '')
            invoice.amount_in_figures = request.form.get('amount_in_figures', '')
            invoice.sync_decimal_fields()

            project_id = request.form.get('project_id', type=int)
            invoice.project_id = project_id

            InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

            form_data = request.form.to_dict(flat=False)
            items_count = 0
            for key in form_data:
                if key.startswith('items[') and key.endswith('][name]'):
                    items_count = max(items_count, int(key.split('[')[1].split(']')[0]) + 1)

            for i in range(items_count):
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

    @bp.route('/invoice/<int:invoice_id>/delete', methods=['GET', 'POST'])
    @login_required
    def invoice_delete(invoice_id):
        invoice = Invoice.query.get_or_404(invoice_id)
        projects = Project.query.order_by(Project.name).all()
        current_project_id = invoice.project_id

        if request.method == 'GET':
            return render_template('confirm_delete.html',
                                   invoice=invoice,
                                   projects=projects,
                                   current_project_id=current_project_id)

        image_path = invoice.image_path
        InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
        db.session.delete(invoice)
        db.session.commit()

        if image_path:
            try:
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

    @bp.route('/invoice/<int:invoice_id>/export/<format>')
    @login_required
    def invoice_export(invoice_id, format):
        try:
            file_path = export_invoice(invoice_id, format, auto_delete=True)
            if not file_path or not os.path.exists(file_path):
                flash('导出失败: 文件生成错误', 'danger')
                return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))
            filename = os.path.basename(file_path)
            from flask import send_file
            return send_file(file_path,
                             as_attachment=True,
                             download_name=filename,
                             mimetype='application/octet-stream')
        except Exception as e:
            flash(f'导出失败: {str(e)}', 'danger')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))

    @bp.route('/invoice/create', methods=['GET', 'POST'])
    @login_required
    def invoice_create():
        projects = Project.query.order_by(Project.name).all()
        today = datetime.now().strftime('%Y-%m-%d')

        if request.method == 'POST':
            try:
                invoice = Invoice()
                invoice.invoice_type = request.form.get('invoice_type', '')
                invoice.invoice_code = request.form.get('invoice_code', '')
                invoice.invoice_number = request.form.get('invoice_number', '')

                invoice_date_str = request.form.get('invoice_date', '')
                if invoice_date_str:
                    try:
                        invoice.invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
                        invoice.invoice_date_raw = invoice_date_str
                    except ValueError:
                        invoice.invoice_date_raw = invoice_date_str

                invoice.seller_name = request.form.get('seller_name', '')
                invoice.seller_tax_id = request.form.get('seller_tax_id', '')
                invoice.buyer_name = request.form.get('buyer_name', '')
                invoice.buyer_tax_id = request.form.get('buyer_tax_id', '')
                invoice.total_amount = request.form.get('total_amount', '')
                invoice.total_tax = request.form.get('total_tax', '')
                invoice.amount_in_figures = request.form.get('amount_in_figures', '')
                invoice.sync_decimal_fields()

                project_id = request.form.get('project_id', type=int)
                invoice.project_id = project_id
                invoice.image_path = None

                db.session.add(invoice)
                db.session.flush()

                current_app.logger.info(f"创建新发票: ID={invoice.id}, 类型={invoice.invoice_type}, 号码={invoice.invoice_number}")

                form_data = request.form.to_dict(flat=False)
                items_added = 0

                for key in form_data:
                    if key.startswith('items[') and key.endswith('][name]'):
                        index = key[6:].split(']')[0]
                        name = form_data.get(f'items[{index}][name]', [''])[0].strip()
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

    @bp.route('/invoice/<int:invoice_id>/rerecognize', methods=['POST'])
    @login_required
    def invoice_rerecognize(invoice_id):
        invoice = Invoice.query.get_or_404(invoice_id)

        if not invoice.image_path:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '该发票没有关联的图片文件，无法重新识别'})
            flash('该发票没有关联的图片文件，无法重新识别', 'danger')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))

        image_path = os.path.join(current_app.root_path, 'static', 'uploads', invoice.image_path)
        if not os.path.exists(image_path):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '图片文件不存在，无法重新识别'})
            flash('图片文件不存在，无法重新识别', 'danger')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))

        result = process_invoice_image(image_path, project_id=invoice.project_id)

        if result.get('success'):
            new_invoice = Invoice.query.get(result['invoice_id'])
            if new_invoice and new_invoice.id != invoice.id:
                InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
                db.session.delete(invoice)
                db.session.commit()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': '重新识别成功，已更新发票信息',
                        'invoice_id': new_invoice.id,
                        'redirect': url_for('main.invoice_detail', invoice_id=new_invoice.id)
                    })
                flash('重新识别成功')
                return redirect(url_for('main.invoice_detail', invoice_id=new_invoice.id))
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': '重新识别完成', 'invoice_id': invoice_id})
                flash('重新识别完成')
                return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': f"重新识别失败: {result.get('message', '未知错误')}"})
            flash(f"重新识别失败: {result.get('message', '未知错误')}", 'danger')
            return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))

    @bp.route('/quick_upload', methods=['POST'])
    @login_required
    def quick_upload():
        from ..models import Settings

        tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID')
        tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY')
        if not (tencent_secret_id and tencent_secret_key):
            flash('请先完成系统设置', 'warning')
            return redirect(url_for('main.settings'))

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
            filename = save_uploaded_file(file)
            if not filename:
                flash('文件保存失败', 'danger')
                return redirect(url_for('main.index'))

            saved_path = os.path.join(current_app.root_path, 'static', 'uploads', filename)
            project_id = request.form.get('project_id', None)
            if project_id == '':
                project_id = None

            result = process_invoice_image(saved_path, project_id=project_id)

            if result.get('success'):
                invoice_id = result.get('invoice_id')
                if project_id:
                    try:
                        project_id = int(project_id)
                        inv = Invoice.query.get(invoice_id)
                        if inv:
                            inv.project_id = project_id
                            db.session.commit()
                    except (ValueError, TypeError):
                        pass
                flash('发票识别成功', 'success')
                return redirect(url_for('main.invoice_detail', invoice_id=invoice_id))
            else:
                flash(f'发票识别失败: {result["message"]}', 'danger')
                return redirect(url_for('main.index'))
        except Exception as e:
            flash(f'处理过程中出错: {str(e)}', 'danger')
            return redirect(url_for('main.index'))

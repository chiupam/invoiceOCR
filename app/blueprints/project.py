import os
from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from ..models import db, Invoice, InvoiceItem, Project
from ..utils import export_project


def register_project_routes(bp):

    @bp.route('/projects')
    @login_required
    def project_list():
        projects = Project.query.order_by(Project.name).all()
        project_stats = {}
        for project in projects:
            invoice_count = Invoice.query.filter_by(project_id=project.id).count()
            project_stats[project.id] = {'invoice_count': invoice_count}
        unclassified_count = Invoice.query.filter_by(project_id=None).count()
        return render_template('project_list.html',
                               projects=projects,
                               project_stats=project_stats,
                               unclassified_count=unclassified_count,
                               current_project_id=None)

    @bp.route('/projects/create', methods=['GET', 'POST'])
    @login_required
    def project_create():
        projects = Project.query.order_by(Project.name).all()
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description', '')
            if not name:
                flash('项目名称不能为空')
                return redirect(url_for('main.project_create'))
            project = Project(name=name, description=description)
            db.session.add(project)
            db.session.commit()
            flash('项目创建成功')
            return redirect(url_for('main.project_list'))
        return render_template('project_form.html',
                               title='创建新项目',
                               projects=projects,
                               current_project_id=None)

    @bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
    @login_required
    def project_edit(project_id):
        project = Project.query.get_or_404(project_id)
        projects = Project.query.order_by(Project.name).all()
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description', '')
            if not name:
                flash('项目名称不能为空')
                return redirect(url_for('main.project_edit', project_id=project_id))
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

    @bp.route('/projects/<int:project_id>/delete', methods=['POST'])
    @login_required
    def project_delete(project_id):
        project = Project.query.get_or_404(project_id)
        handle_invoices = request.form.get('handle_invoices', 'unclassify')
        if handle_invoices == 'unclassify':
            Invoice.query.filter_by(project_id=project_id).update({Invoice.project_id: None})
        elif handle_invoices == 'delete':
            invoices = Invoice.query.filter_by(project_id=project_id).all()
            for invoice in invoices:
                InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
                db.session.delete(invoice)
        db.session.delete(project)
        db.session.commit()
        flash('项目已删除')
        return redirect(url_for('main.project_list'))

    @bp.route('/project/<int:project_id>')
    @login_required
    def project_detail(project_id):
        project = Project.query.get_or_404(project_id)
        invoices = Invoice.query.filter_by(project_id=project_id).all()
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return render_template('project_detail.html',
                               title=f'项目: {project.name}',
                               project=project,
                               invoices=invoices,
                               projects=projects,
                               current_project_id=project_id)

    @bp.route('/project/<int:project_id>/export')
    @login_required
    def project_export(project_id):
        try:
            file_path = export_project(project_id, auto_delete=True)
            if not file_path or not os.path.exists(file_path):
                flash('导出失败: 文件生成错误', 'danger')
                return redirect(url_for('main.project_detail', project_id=project_id))
            filename = os.path.basename(file_path)
            return send_file(file_path,
                             as_attachment=True,
                             download_name=filename,
                             mimetype='application/octet-stream')
        except Exception as e:
            flash(f'导出失败: {str(e)}', 'danger')
            return redirect(url_for('main.project_detail', project_id=project_id))

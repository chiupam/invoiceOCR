from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..models import Settings


def register_settings_routes(bp):

    @bp.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        if request.method == 'POST':
            tencent_secret_id = request.form.get('tencent_secret_id', '').strip()
            tencent_secret_key = request.form.get('tencent_secret_key', '').strip()
            if not tencent_secret_id or not tencent_secret_key:
                flash('请填写所有必填字段', 'danger')
                return redirect(url_for('main.settings'))
            Settings.set_value('TENCENT_SECRET_ID', tencent_secret_id)
            Settings.set_value('TENCENT_SECRET_KEY', tencent_secret_key)
            flash('设置已保存', 'success')
            return redirect(url_for('main.index'))

        tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID', '')
        tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY', '')
        return render_template('settings.html',
                               tencent_secret_id=tencent_secret_id,
                               tencent_secret_key=tencent_secret_key)

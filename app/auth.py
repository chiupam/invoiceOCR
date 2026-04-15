#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import re
import qrcode
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError
from app import limiter
from app.models import db, User

auth = Blueprint('auth', __name__)


class LoginForm(FlaskForm):
    password = PasswordField('密码', validators=[DataRequired()])
    remember = BooleanField('记住我')
    submit = SubmitField('登录')


class SetupForm(FlaskForm):
    password = PasswordField('密码', validators=[
        DataRequired(message='请输入密码'),
        Length(min=8, max=128, message='密码长度至少8位')
    ])
    password2 = PasswordField('确认密码', validators=[
        DataRequired(message='请再次输入密码'),
        EqualTo('password', message='两次输入的密码不一致')
    ])
    submit = SubmitField('完成设置')

    def validate_password(self, field):
        password = field.data
        if password:
            if not re.search(r'[A-Za-z]', password):
                raise ValidationError('密码必须包含至少一个字母')
            if not re.search(r'[0-9]', password):
                raise ValidationError('密码必须包含至少一个数字')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('当前密码', validators=[DataRequired(message='请输入当前密码')])
    new_password = PasswordField('新密码', validators=[
        DataRequired(message='请输入新密码'),
        Length(min=8, max=128, message='密码长度至少8位')
    ])
    new_password2 = PasswordField('确认新密码', validators=[
        DataRequired(message='请再次输入新密码'),
        EqualTo('new_password', message='两次输入的密码不一致')
    ])
    submit = SubmitField('修改密码')

    def validate_new_password(self, field):
        password = field.data
        if password:
            if not re.search(r'[A-Za-z]', password):
                raise ValidationError('密码必须包含至少一个字母')
            if not re.search(r'[0-9]', password):
                raise ValidationError('密码必须包含至少一个数字')
        if current_user.check_password(field.data):
            raise ValidationError('新密码不能与当前密码相同')


class MFAVerifyForm(FlaskForm):
    code = PasswordField('验证码', validators=[DataRequired(message='请输入验证码'), Length(6, 6, message='验证码为6位数字')])
    submit = SubmitField('验证')


class MFASetupForm(FlaskForm):
    code = PasswordField('验证码', validators=[DataRequired(message='请输入验证码'), Length(6, 6, message='验证码为6位数字')])
    submit = SubmitField('启用')


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute", methods=['GET'])
@limiter.limit("20 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if not User.get_owner():
        return redirect(url_for('auth.setup'))

    user = User.get_owner()
    is_locked = user.is_locked() if user else False
    lock_remaining = 0

    if is_locked and user.locked_until:
        from datetime import datetime
        delta = user.locked_until - datetime.now()
        lock_remaining = max(0, int(delta.total_seconds()))

    form = LoginForm()
    if form.validate_on_submit():
        if is_locked:
            return redirect(url_for('auth.login'))

        password = form.password.data

        if not user.check_password(password):
            user.increment_failed_login()
            remaining = 5 - user.failed_login_count
            if remaining > 0:
                flash(f'密码错误，还剩{remaining}次尝试机会', 'danger')
            else:
                flash('密码错误次数过多，账户已锁定15分钟', 'danger')
            return redirect(url_for('auth.login'))

        if user.mfa_enabled:
            session['mfa_user_id'] = user.id
            session['mfa_remember'] = form.remember.data
            return redirect(url_for('auth.mfa_verify'))

        login_user(user, remember=form.remember.data)
        user.record_login(request.remote_addr)
        session.permanent = True
        flash('登录成功', 'success')

        next_page = request.args.get('next')
        if next_page and not next_page.startswith('/'):
            next_page = None
        return redirect(next_page or url_for('main.index'))

    return render_template('auth/login.html', form=form, is_locked=is_locked, lock_remaining=lock_remaining)


@auth.route('/login/mfa', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def mfa_verify():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    mfa_user_id = session.get('mfa_user_id')
    if not mfa_user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(mfa_user_id)
    if not user or not user.mfa_enabled:
        session.pop('mfa_user_id', None)
        return redirect(url_for('auth.login'))

    form = MFAVerifyForm()
    if form.validate_on_submit():
        code = form.code.data.strip()
        if user.verify_mfa_code(code):
            session.pop('mfa_user_id', None)
            remember = session.pop('mfa_remember', False)
            login_user(user, remember=remember)
            user.record_login(request.remote_addr)
            session.permanent = True
            flash('登录成功', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('验证码错误，请重试', 'danger')

    return render_template('auth/mfa_verify.html', form=form)


@auth.route('/setup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def setup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if not User.can_register():
        return redirect(url_for('auth.login'))

    form = SetupForm()
    if form.validate_on_submit():
        try:
            user = User(
                username='owner',
                email='owner@invoice-ocr.local',
                is_admin=True
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            login_user(user, remember=True)
            user.record_login(request.remote_addr)
            session.permanent = True
            flash('账户设置成功，欢迎使用发票OCR系统', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash('账户创建失败，请重试', 'danger')
            current_app.logger.error(f'用户创建失败: {e}')

    return render_template('auth/setup.html', form=form)


@auth.route('/register')
def register():
    if not User.can_register():
        flash('已完成初始设置', 'warning')
        return redirect(url_for('auth.login'))
    return redirect(url_for('auth.setup'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('已安全退出', 'info')
    return redirect(url_for('auth.login'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('当前密码错误', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('密码修改成功，请重新登录', 'success')
        logout_user()
        return redirect(url_for('auth.login'))

    return render_template('auth/change_password.html', form=form)


@auth.route('/mfa/setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    form = MFASetupForm()

    if current_user.mfa_enabled:
        return redirect(url_for('auth.mfa_manage'))

    if request.method == 'GET':
        if not current_user.mfa_secret:
            current_user.generate_mfa_secret()
            db.session.commit()

    if form.validate_on_submit():
        code = form.code.data.strip()
        if current_user.verify_mfa_code(code):
            current_user.mfa_enabled = True
            db.session.commit()
            session['mfa_just_enabled'] = True
            flash('两步验证已成功启用', 'success')
            return redirect(url_for('auth.mfa_manage'))
        else:
            flash('验证码错误，请重试', 'danger')

    mfa_uri = current_user.get_mfa_uri()
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(mfa_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    import base64
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('auth/mfa_setup.html', form=form, qr_b64=qr_b64, secret=current_user.mfa_secret)


@auth.route('/mfa/manage', methods=['GET', 'POST'])
@login_required
def mfa_manage():
    just_enabled = session.pop('mfa_just_enabled', False)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'disable':
            current_user.mfa_enabled = False
            current_user.mfa_secret = None
            db.session.commit()
            flash('两步验证已关闭', 'info')
            return redirect(url_for('auth.mfa_manage'))

    return render_template('auth/mfa_manage.html', mfa_enabled=current_user.mfa_enabled, just_enabled=just_enabled)


@auth.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

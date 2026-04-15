#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import decimal
import pyotp
import bcrypt
import secrets
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(32), nullable=True)

    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    MAX_USERS = 1

    @classmethod
    def can_register(cls):
        return cls.query.count() < cls.MAX_USERS

    @classmethod
    def get_owner(cls):
        return cls.query.first()

    def set_password(self, password):
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    def check_password(self, password):
        if not self.password_hash:
            return False
        if self.password_hash.startswith('pbkdf2:'):
            result = check_password_hash(self.password_hash, password)
            if result:
                self.set_password(password)
                db.session.commit()
            return result
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except (ValueError, TypeError):
            return False

    def generate_mfa_secret(self):
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret

    def get_mfa_uri(self, issuer_name='发票OCR系统'):
        if not self.mfa_secret:
            self.generate_mfa_secret()
        return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
            name=self.email, issuer_name=issuer_name
        )

    def verify_mfa_code(self, code):
        if not self.mfa_secret:
            return False
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(code, valid_window=1)

    def is_locked(self):
        if self.locked_until and self.locked_until > datetime.now():
            return True
        if self.locked_until and self.locked_until <= datetime.now():
            self.locked_until = None
            self.failed_login_count = 0
            db.session.commit()
        return False

    def increment_failed_login(self):
        if self.failed_login_count is None:
            self.failed_login_count = 0
        self.failed_login_count += 1
        if self.failed_login_count >= 5:
            from datetime import timedelta
            self.locked_until = datetime.now() + timedelta(minutes=15)
        db.session.commit()

    def reset_failed_login(self):
        self.failed_login_count = 0
        self.locked_until = None
        db.session.commit()

    def record_login(self, ip_address):
        self.last_login_at = datetime.now()
        self.last_login_ip = ip_address
        self.reset_failed_login()

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username}>'


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    invoices = db.relationship('Invoice', backref='project', lazy=True)

    def __repr__(self):
        return f'<Project {self.name}>'


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    invoice_type = db.Column(db.String(50), nullable=True)
    invoice_code = db.Column(db.String(50), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True)
    invoice_date_raw = db.Column(db.String(50), nullable=True)
    check_code = db.Column(db.String(100), nullable=True)
    machine_number = db.Column(db.String(50), nullable=True)

    seller_name = db.Column(db.String(100), nullable=True)
    seller_tax_id = db.Column(db.String(50), nullable=True)
    seller_address = db.Column(db.String(200), nullable=True)
    seller_bank_info = db.Column(db.String(200), nullable=True)

    buyer_name = db.Column(db.String(100), nullable=True)
    buyer_tax_id = db.Column(db.String(50), nullable=True)
    buyer_address = db.Column(db.String(200), nullable=True)
    buyer_bank_info = db.Column(db.String(200), nullable=True)

    total_amount = db.Column(db.String(50), nullable=True)
    total_tax = db.Column(db.String(50), nullable=True)
    amount_in_words = db.Column(db.String(100), nullable=True)
    amount_in_figures = db.Column(db.String(50), nullable=True)

    remarks = db.Column(db.String(200), nullable=True)
    payee = db.Column(db.String(50), nullable=True)
    reviewer = db.Column(db.String(50), nullable=True)
    issuer = db.Column(db.String(50), nullable=True)

    image_path = db.Column(db.String(200), nullable=True)
    json_data = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('invoice_code', 'invoice_number', name='uix_invoice_code_number'),
    )

    @property
    def combined_id(self):
        if self.invoice_number:
            if self.invoice_code:
                return f"{self.invoice_code}{self.invoice_number}"
            else:
                return f"NO.{self.invoice_number}"
        return f"ID{self.id}"

    def get_total_amount_decimal(self):
        try:
            amount_str = self.amount_in_figures or '0'
            cleaned_amount = amount_str.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '')
            return Decimal(cleaned_amount)
        except (ValueError, TypeError, decimal.InvalidOperation):
            return Decimal('0')

    @classmethod
    def from_formatted_data(cls, formatted_data, image_path=None):
        basic_info = formatted_data.get('基本信息', {})
        seller_info = formatted_data.get('销售方信息', {})
        buyer_info = formatted_data.get('购买方信息', {})
        amount_info = formatted_data.get('金额信息', {})
        other_info = formatted_data.get('其他信息', {})

        invoice_date_raw = basic_info.get('开票日期', '')
        invoice_date = None
        if '开票日期标准格式' in basic_info and basic_info['开票日期标准格式']:
            try:
                invoice_date = datetime.strptime(basic_info['开票日期标准格式'], '%Y-%m-%d').date()
            except ValueError:
                pass

        invoice = cls(
            invoice_type=basic_info.get('发票类型', ''),
            invoice_code=basic_info.get('发票代码', ''),
            invoice_number=basic_info.get('发票号码', ''),
            invoice_date=invoice_date,
            invoice_date_raw=invoice_date_raw,
            check_code=basic_info.get('校验码', ''),
            machine_number=basic_info.get('机器编号', ''),
            seller_name=seller_info.get('名称', ''),
            seller_tax_id=seller_info.get('识别号', ''),
            seller_address=seller_info.get('地址电话', ''),
            seller_bank_info=seller_info.get('开户行及账号', ''),
            buyer_name=buyer_info.get('名称', ''),
            buyer_tax_id=buyer_info.get('识别号', ''),
            buyer_address=buyer_info.get('地址电话', ''),
            buyer_bank_info=buyer_info.get('开户行及账号', ''),
            total_amount=amount_info.get('合计金额', ''),
            total_tax=amount_info.get('合计税额', ''),
            amount_in_words=amount_info.get('价税合计(大写)', ''),
            amount_in_figures=amount_info.get('价税合计(小写)', ''),
            remarks=other_info.get('备注', ''),
            payee=other_info.get('收款人', ''),
            reviewer=other_info.get('复核', ''),
            issuer=other_info.get('开票人', ''),
            image_path=image_path,
            json_data=json.dumps(formatted_data, ensure_ascii=False)
        )

        return invoice

    def get_items(self):
        if not self.json_data:
            return []
        try:
            data = json.loads(self.json_data)
            return data.get('商品信息', [])
        except (json.JSONDecodeError, AttributeError):
            return []


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)

    name = db.Column(db.String(100), nullable=True)
    specification = db.Column(db.String(100), nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.String(50), nullable=True)
    price = db.Column(db.String(50), nullable=True)
    amount = db.Column(db.String(50), nullable=True)
    tax_rate = db.Column(db.String(20), nullable=True)
    tax = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now)

    invoice = db.relationship('Invoice', backref=db.backref('items', lazy=True))

    @classmethod
    def from_item_data(cls, invoice_id, item_data):
        return cls(
            invoice_id=invoice_id,
            name=item_data.get('Name', item_data.get('项目名称', item_data.get('LineNo', ''))),
            specification=item_data.get('Specification', item_data.get('规格型号', item_data.get('Spec', ''))),
            unit=item_data.get('Unit', item_data.get('单位', '')),
            quantity=item_data.get('Quantity', item_data.get('数量', '')),
            price=item_data.get('Price', item_data.get('单价', item_data.get('UnitPrice', ''))),
            amount=item_data.get('Amount', item_data.get('金额', item_data.get('AmountWithoutTax', ''))),
            tax_rate=item_data.get('TaxRate', item_data.get('税率', '')),
            tax=item_data.get('Tax', item_data.get('税额', item_data.get('TaxAmount', '')))
        )


class Settings(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @classmethod
    def get_value(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_value(cls, key, value):
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        return setting

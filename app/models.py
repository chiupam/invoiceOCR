#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import decimal
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal

db = SQLAlchemy()

class Project(db.Model):
    """项目模型 - 用于发票分类管理"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 反向关联发票
    invoices = db.relationship('Invoice', backref='project', lazy=True)
    
    def __repr__(self):
        return f'<Project {self.name}>'

class Invoice(db.Model):
    """发票数据模型"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    # 基本信息
    invoice_type = db.Column(db.String(50), nullable=True)  # 发票类型
    invoice_code = db.Column(db.String(50), nullable=True)  # 发票代码
    invoice_number = db.Column(db.String(50), nullable=True)  # 发票号码
    invoice_date = db.Column(db.Date, nullable=True)  # 开票日期
    invoice_date_raw = db.Column(db.String(50), nullable=True)  # 原始开票日期文本
    check_code = db.Column(db.String(100), nullable=True)  # 校验码
    machine_number = db.Column(db.String(50), nullable=True)  # 机器编号
    
    # 销售方信息
    seller_name = db.Column(db.String(100), nullable=True)  # 销售方名称
    seller_tax_id = db.Column(db.String(50), nullable=True)  # 销售方识别号
    seller_address = db.Column(db.String(200), nullable=True)  # 销售方地址电话
    seller_bank_info = db.Column(db.String(200), nullable=True)  # 销售方开户行及账号
    
    # 购买方信息
    buyer_name = db.Column(db.String(100), nullable=True)  # 购买方名称
    buyer_tax_id = db.Column(db.String(50), nullable=True)  # 购买方识别号
    buyer_address = db.Column(db.String(200), nullable=True)  # 购买方地址电话
    buyer_bank_info = db.Column(db.String(200), nullable=True)  # 购买方开户行及账号
    
    # 金额信息
    total_amount = db.Column(db.String(50), nullable=True)  # 合计金额
    total_tax = db.Column(db.String(50), nullable=True)  # 合计税额
    amount_in_words = db.Column(db.String(100), nullable=True)  # 价税合计(大写)
    amount_in_figures = db.Column(db.String(50), nullable=True)  # 价税合计(小写)
    
    # 其他信息
    remarks = db.Column(db.String(200), nullable=True)  # 备注
    payee = db.Column(db.String(50), nullable=True)  # 收款人
    reviewer = db.Column(db.String(50), nullable=True)  # 复核
    issuer = db.Column(db.String(50), nullable=True)  # 开票人
    
    # 文件信息
    image_path = db.Column(db.String(200), nullable=True)  # 图片路径
    json_data = db.Column(db.Text, nullable=True)  # 完整JSON数据
    
    # 处理信息
    created_at = db.Column(db.DateTime, default=datetime.now)  # 创建时间
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)  # 更新时间
    
    # 添加项目关联
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    
    # 确保发票代码+发票号码的组合是唯一的
    __table_args__ = (
        db.UniqueConstraint('invoice_code', 'invoice_number', name='uix_invoice_code_number'),
    )
    
    @property
    def combined_id(self):
        """返回发票代码+发票号码的组合ID"""
        # 普通发票可能没有代码，只有号码
        if self.invoice_number:
            if self.invoice_code:
                return f"{self.invoice_code}{self.invoice_number}"
            else:
                return f"NO.{self.invoice_number}"
        return f"ID{self.id}"  # 如果缺少代码和号码，则返回数据库ID
    
    def get_total_amount_decimal(self):
        """
        获取发票合计金额的小数形式
        
        返回:
            浮点数形式的金额，如果转换失败则返回0
        """
        if not self.total_amount:
            return 0
            
        try:
            # 处理金额字符串，去除非数字字符（如货币符号、逗号等）
            amount_str = self.total_amount.replace('¥', '').replace(',', '').strip()
            return float(amount_str)
        except (ValueError, TypeError):
            return 0
    
    @classmethod
    def from_formatted_data(cls, formatted_data, image_path=None):
        """
        从格式化后的发票数据创建发票对象
        
        参数:
            formatted_data: 格式化后的发票数据（字典）
            image_path: 发票图片路径
            
        返回:
            发票对象
        """
        # 提取各部分数据
        basic_info = formatted_data.get('基本信息', {})
        seller_info = formatted_data.get('销售方信息', {})
        buyer_info = formatted_data.get('购买方信息', {})
        amount_info = formatted_data.get('金额信息', {})
        other_info = formatted_data.get('其他信息', {})
        
        # 处理日期字符串
        invoice_date_raw = basic_info.get('开票日期', '')
        invoice_date = None
        if '开票日期标准格式' in basic_info and basic_info['开票日期标准格式']:
            try:
                invoice_date = datetime.strptime(basic_info['开票日期标准格式'], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # 创建发票对象
        invoice = cls(
            # 基本信息
            invoice_type=basic_info.get('发票类型', ''),
            invoice_code=basic_info.get('发票代码', ''),
            invoice_number=basic_info.get('发票号码', ''),
            invoice_date=invoice_date,
            invoice_date_raw=invoice_date_raw,
            check_code=basic_info.get('校验码', ''),
            machine_number=basic_info.get('机器编号', ''),
            
            # 销售方信息
            seller_name=seller_info.get('名称', ''),
            seller_tax_id=seller_info.get('识别号', ''),
            seller_address=seller_info.get('地址电话', ''),
            seller_bank_info=seller_info.get('开户行及账号', ''),
            
            # 购买方信息
            buyer_name=buyer_info.get('名称', ''),
            buyer_tax_id=buyer_info.get('识别号', ''),
            buyer_address=buyer_info.get('地址电话', ''),
            buyer_bank_info=buyer_info.get('开户行及账号', ''),
            
            # 金额信息
            total_amount=amount_info.get('合计金额', ''),
            total_tax=amount_info.get('合计税额', ''),
            amount_in_words=amount_info.get('价税合计(大写)', ''),
            amount_in_figures=amount_info.get('价税合计(小写)', ''),
            
            # 其他信息
            remarks=other_info.get('备注', ''),
            payee=other_info.get('收款人', ''),
            reviewer=other_info.get('复核', ''),
            issuer=other_info.get('开票人', ''),
            
            # 文件信息
            image_path=image_path,
            json_data=json.dumps(formatted_data, ensure_ascii=False)
        )
        
        return invoice
    
    def get_items(self):
        """获取发票商品项目列表"""
        if not self.json_data:
            return []
        
        try:
            data = json.loads(self.json_data)
            return data.get('商品信息', [])
        except (json.JSONDecodeError, AttributeError):
            return []
    
    def get_total_amount_decimal(self):
        """获取发票金额(小写)为Decimal类型"""
        try:
            # 移除可能的货币符号和空格，然后转换为Decimal
            amount_str = self.amount_in_figures or '0'
            # 移除可能的¥符号、空格以及"元"字
            cleaned_amount = amount_str.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '')
            return Decimal(cleaned_amount)
        except (ValueError, TypeError, decimal.InvalidOperation):
            return Decimal('0')


class InvoiceItem(db.Model):
    """发票项目数据模型（用于存储发票中的商品项目）"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=True)  # 商品名称
    specification = db.Column(db.String(100), nullable=True)  # 规格型号
    unit = db.Column(db.String(20), nullable=True)  # 单位
    quantity = db.Column(db.String(50), nullable=True)  # 数量
    price = db.Column(db.String(50), nullable=True)  # 单价
    amount = db.Column(db.String(50), nullable=True)  # 金额
    tax_rate = db.Column(db.String(20), nullable=True)  # 税率
    tax = db.Column(db.String(50), nullable=True)  # 税额
    
    created_at = db.Column(db.DateTime, default=datetime.now)  # 创建时间
    
    # 定义与发票的关系
    invoice = db.relationship('Invoice', backref=db.backref('items', lazy=True))
    
    @classmethod
    def from_item_data(cls, invoice_id, item_data):
        """
        从商品项目数据创建商品对象
        
        参数:
            invoice_id: 关联的发票ID
            item_data: 商品项目数据（字典）
            
        返回:
            商品对象
        """
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
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import json
from datetime import datetime

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import Invoice, InvoiceItem, Settings

def json_serial(obj):
    """处理JSON序列化时无法处理的类型"""
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    raise TypeError(f"Type {type(obj)} not serializable")

def query_invoices(invoice_id=None, limit=None, output_format='text'):
    """查询数据库中的发票信息"""
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    with app.app_context():
        if invoice_id:
            # 查询特定ID的发票
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                print(f"未找到ID为{invoice_id}的发票")
                return
            
            invoices = [invoice]
        else:
            # 查询所有发票，可能有数量限制
            query = Invoice.query.order_by(Invoice.invoice_date.desc())
            if limit:
                query = query.limit(limit)
            invoices = query.all()
        
        if not invoices:
            print("数据库中没有发票记录")
            return
        
        if output_format == 'json':
            # 输出JSON格式
            result = []
            for invoice in invoices:
                inv_dict = {
                    'id': invoice.id,
                    'invoice_type': invoice.invoice_type,
                    'invoice_code': invoice.invoice_code,
                    'invoice_number': invoice.invoice_number,
                    'invoice_date': invoice.invoice_date,
                    'seller_name': invoice.seller_name,
                    'buyer_name': invoice.buyer_name,
                    'total_amount': invoice.total_amount,
                    'total_tax': invoice.total_tax,
                    'created_at': invoice.created_at,
                    'updated_at': invoice.updated_at,
                    'image_path': invoice.image_path,
                    'items': []
                }
                
                for item in invoice.items:
                    item_dict = {
                        'id': item.id,
                        'name': item.name,
                        'specification': item.specification,
                        'unit': item.unit,
                        'quantity': item.quantity,
                        'price': item.price,
                        'amount': item.amount,
                        'tax_rate': item.tax_rate,
                        'tax': item.tax
                    }
                    inv_dict['items'].append(item_dict)
                
                result.append(inv_dict)
            
            print(json.dumps(result, ensure_ascii=False, indent=2, default=json_serial))
        else:
            # 输出文本表格格式
            for invoice in invoices:
                print("\n" + "="*80)
                print(f"发票ID: {invoice.id}")
                print(f"类型: {invoice.invoice_type}")
                print(f"代码: {invoice.invoice_code}")
                print(f"号码: {invoice.invoice_number}")
                print(f"日期: {invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '未知'}")
                print(f"销售方: {invoice.seller_name}")
                print(f"购买方: {invoice.buyer_name}")
                print(f"金额: {invoice.total_amount}")
                print(f"税额: {invoice.total_tax}")
                print(f"创建时间: {invoice.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"更新时间: {invoice.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"图片路径: {invoice.image_path}")
                
                print("-"*40)
                print("发票明细项:")
                if invoice.items:
                    for idx, item in enumerate(invoice.items, 1):
                        print(f"  项目{idx}:")
                        print(f"    名称: {item.name}")
                        print(f"    规格: {item.specification or '-'}")
                        print(f"    单位: {item.unit or '-'}")
                        print(f"    数量: {item.quantity or '-'}")
                        print(f"    单价: {item.price or '-'}")
                        print(f"    金额: {item.amount}")
                        print(f"    税率: {item.tax_rate}")
                        print(f"    税额: {item.tax}")
                else:
                    print("  无明细项")
                
                print("="*80)

def count_db_stats():
    """统计数据库中的各类记录数量"""
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    with app.app_context():
        invoice_count = Invoice.query.count()
        item_count = InvoiceItem.query.count()
        
        # 发票类型统计
        invoice_types = {}
        for invoice in Invoice.query.all():
            if invoice.invoice_type:
                invoice_types[invoice.invoice_type] = invoice_types.get(invoice.invoice_type, 0) + 1
        
        # 计算总金额
        total_amount = 0
        for invoice in Invoice.query.all():
            if invoice.total_amount:
                try:
                    amount = float(invoice.total_amount.replace('¥', '').strip())
                    total_amount += amount
                except ValueError:
                    pass
        
        print("\n数据库统计信息:")
        print("-"*40)
        print(f"发票总数: {invoice_count}")
        print(f"发票明细项总数: {item_count}")
        print(f"总金额: ¥{total_amount:.2f}")
        
        print("\n发票类型分布:")
        for type_name, count in invoice_types.items():
            print(f"  {type_name}: {count}张")

def query_settings(key=None, output_format='text'):
    """查询数据库中的系统设置"""
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    with app.app_context():
        if key:
            # 查询特定key的设置
            setting = Settings.query.filter_by(key=key).first()
            if not setting:
                print(f"未找到key为{key}的设置")
                return
            
            settings = [setting]
        else:
            # 查询所有设置
            settings = Settings.query.all()
        
        if not settings:
            print("数据库中没有系统设置记录")
            return
        
        if output_format == 'json':
            # 输出JSON格式
            result = []
            for setting in settings:
                setting_dict = {
                    'id': setting.id,
                    'key': setting.key,
                    'value': setting.value,
                    'updated_at': setting.updated_at
                }
                result.append(setting_dict)
            
            print(json.dumps(result, ensure_ascii=False, indent=2, default=json_serial))
        else:
            # 输出文本表格格式
            print("\n系统设置:")
            print("-"*60)
            for setting in settings:
                print(f"ID: {setting.id}")
                print(f"键名: {setting.key}")
                # 对于API密钥等敏感信息，只显示部分字符
                if 'secret' in setting.key.lower() and setting.value:
                    masked_value = setting.value[:4] + '*' * (len(setting.value) - 8) + setting.value[-4:] if len(setting.value) > 8 else '******'
                    print(f"值: {masked_value} (已隐藏部分字符)")
                else:
                    print(f"值: {setting.value}")
                print(f"更新时间: {setting.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print("-"*60)

def main():
    parser = argparse.ArgumentParser(description='发票OCR系统数据库查询工具')
    parser.add_argument('--id', type=int, help='查询特定ID的发票')
    parser.add_argument('--limit', type=int, help='限制查询结果数量')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式（文本或JSON）')
    parser.add_argument('--stats', action='store_true', help='显示数据库统计信息')
    parser.add_argument('--settings', action='store_true', help='查询系统设置')
    parser.add_argument('--key', type=str, help='查询特定键名的系统设置')
    args = parser.parse_args()
    
    if args.settings or args.key:
        query_settings(key=args.key, output_format=args.format)
    elif args.stats:
        count_db_stats()
    else:
        query_invoices(invoice_id=args.id, limit=args.limit, output_format=args.format)

if __name__ == '__main__':
    main() 
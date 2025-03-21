#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import csv
import os
import sys
from datetime import datetime

class InvoiceExporter:
    """发票数据导出工具类"""
    
    @staticmethod
    def export_to_csv(invoice_data, output_path=None):
        """
        将发票数据导出为CSV格式
        
        参数:
            invoice_data: 格式化后的发票数据（字典）
            output_path: 输出CSV文件的路径
        
        返回:
            CSV文件路径
        """
        if output_path is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "data/output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, f"invoice_{timestamp_str}.csv")
        
        # 提取发票基本信息
        basic_info = invoice_data.get('基本信息', {})
        seller_info = invoice_data.get('销售方信息', {})
        buyer_info = invoice_data.get('购买方信息', {})
        amount_info = invoice_data.get('金额信息', {})
        other_info = invoice_data.get('其他信息', {})
        
        # 准备表头和基本数据行
        headers = [
            '发票类型', '发票代码', '发票号码', '开票日期', 
            '销售方名称', '销售方识别号', 
            '购买方名称', '购买方识别号', 
            '合计金额', '合计税额', '价税合计(小写)', 
            '商品名称', '规格型号', '单位', '数量', '单价', '金额', '税率', '税额'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            # 获取商品信息列表
            items = invoice_data.get('商品信息', [])
            
            if items:
                # 有商品项目，每个商品一行
                for item in items:
                    row = [
                        basic_info.get('发票类型', ''),
                        basic_info.get('发票代码', ''),
                        basic_info.get('发票号码', ''),
                        basic_info.get('开票日期', ''),
                        seller_info.get('名称', ''),
                        seller_info.get('识别号', ''),
                        buyer_info.get('名称', ''),
                        buyer_info.get('识别号', ''),
                        amount_info.get('合计金额', ''),
                        amount_info.get('合计税额', ''),
                        amount_info.get('价税合计(小写)', ''),
                        item.get('Name', ''),
                        item.get('Specification', ''),
                        item.get('Unit', ''),
                        item.get('Quantity', ''),
                        item.get('Price', ''),
                        item.get('Amount', ''),
                        item.get('TaxRate', ''),
                        item.get('Tax', '')
                    ]
                    writer.writerow(row)
            else:
                # 没有商品项目，只写一行基本信息
                row = [
                    basic_info.get('发票类型', ''),
                    basic_info.get('发票代码', ''),
                    basic_info.get('发票号码', ''),
                    basic_info.get('开票日期', ''),
                    seller_info.get('名称', ''),
                    seller_info.get('识别号', ''),
                    buyer_info.get('名称', ''),
                    buyer_info.get('识别号', ''),
                    amount_info.get('合计金额', ''),
                    amount_info.get('合计税额', ''),
                    amount_info.get('价税合计(小写)', ''),
                    '', '', '', '', '', '', '', ''  # 商品相关字段为空
                ]
                writer.writerow(row)
        
        return output_path

    @staticmethod
    def export_to_excel(invoice_data, output_path=None):
        """
        将发票数据导出为Excel格式（需要安装pandas和openpyxl）
        
        参数:
            invoice_data: 格式化后的发票数据（字典）
            output_path: 输出Excel文件的路径
        
        返回:
            Excel文件路径
        """
        try:
            import pandas as pd
        except ImportError:
            print("导出Excel格式需要安装pandas和openpyxl库")
            print("请运行: pip install pandas openpyxl")
            return None
        
        if output_path is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "data/output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, f"invoice_{timestamp_str}.xlsx")
        
        # 提取发票基本信息
        basic_info = invoice_data.get('基本信息', {})
        seller_info = invoice_data.get('销售方信息', {})
        buyer_info = invoice_data.get('购买方信息', {})
        amount_info = invoice_data.get('金额信息', {})
        other_info = invoice_data.get('其他信息', {})
        
        # 基本发票信息表
        basic_df = pd.DataFrame({
            '项目': [
                '发票类型', '发票代码', '发票号码', '开票日期', '校验码', '机器编号',
                '销售方名称', '销售方识别号', '销售方地址电话', '销售方开户行及账号',
                '购买方名称', '购买方识别号', '购买方地址电话', '购买方开户行及账号',
                '合计金额', '合计税额', '价税合计(大写)', '价税合计(小写)',
                '备注', '收款人', '复核', '开票人'
            ],
            '内容': [
                basic_info.get('发票类型', ''),
                basic_info.get('发票代码', ''),
                basic_info.get('发票号码', ''),
                basic_info.get('开票日期', ''),
                basic_info.get('校验码', ''),
                basic_info.get('机器编号', ''),
                seller_info.get('名称', ''),
                seller_info.get('识别号', ''),
                seller_info.get('地址电话', ''),
                seller_info.get('开户行及账号', ''),
                buyer_info.get('名称', ''),
                buyer_info.get('识别号', ''),
                buyer_info.get('地址电话', ''),
                buyer_info.get('开户行及账号', ''),
                amount_info.get('合计金额', ''),
                amount_info.get('合计税额', ''),
                amount_info.get('价税合计(大写)', ''),
                amount_info.get('价税合计(小写)', ''),
                other_info.get('备注', ''),
                other_info.get('收款人', ''),
                other_info.get('复核', ''),
                other_info.get('开票人', '')
            ]
        })
        
        # 创建Excel写入器
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # 写入发票基本信息
            basic_df.to_excel(writer, sheet_name='发票基本信息', index=False)
            
            # 获取商品信息列表
            items = invoice_data.get('商品信息', [])
            if items:
                # 处理商品明细信息
                items_data = []
                for item in items:
                    items_data.append({
                        '商品名称': item.get('Name', ''),
                        '规格型号': item.get('Specification', ''),
                        '单位': item.get('Unit', ''),
                        '数量': item.get('Quantity', ''),
                        '单价': item.get('Price', ''),
                        '金额': item.get('Amount', ''),
                        '税率': item.get('TaxRate', ''),
                        '税额': item.get('Tax', '')
                    })
                items_df = pd.DataFrame(items_data)
                items_df.to_excel(writer, sheet_name='商品明细', index=False)
        
        return output_path

    @staticmethod
    def process_json_to_exports(json_file, formats=None):
        """
        处理JSON文件并导出为多种格式
        
        参数:
            json_file: JSON文件路径
            formats: 导出格式列表，可选值：'csv', 'excel'
        """
        if formats is None:
            formats = ['csv']
            
        try:
            # 读取JSON文件
            with open(json_file, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)
            
            results = {}
            
            # 导出为CSV
            if 'csv' in formats:
                csv_path = InvoiceExporter.export_to_csv(invoice_data)
                if csv_path:
                    print(f"发票数据已导出为CSV: {csv_path}")
                    results['csv'] = csv_path
            
            # 导出为Excel
            if 'excel' in formats:
                excel_path = InvoiceExporter.export_to_excel(invoice_data)
                if excel_path:
                    print(f"发票数据已导出为Excel: {excel_path}")
                    results['excel'] = excel_path
            
            return results
        
        except Exception as e:
            print(f"导出发票数据时出错: {e}")
            return {}

    @staticmethod
    def export_project_to_excel(project_data, invoices, output_path=None):
        """
        将项目数据和相关发票导出为Excel格式
        
        参数:
            project_data: 项目信息（字典）
            invoices: 项目下的发票列表
            output_path: 输出Excel文件的路径
        
        返回:
            Excel文件路径
        """
        try:
            import pandas as pd
            import numpy as np
            from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
            from openpyxl.chart import BarChart, PieChart, Reference
            from openpyxl.chart.label import DataLabelList
        except ImportError:
            print("导出Excel格式需要安装pandas和openpyxl库")
            print("请运行: pip install pandas openpyxl")
            return None
        
        if output_path is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 使用绝对路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "data", "output")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            # 使用项目名称作为文件名的一部分
            safe_name = "".join(x for x in project_data.get('name', '') if x.isalnum() or x in "._- ")
            output_path = os.path.join(output_dir, f"project_{safe_name}_{timestamp_str}.xlsx")
        
        # 创建空的Excel文件
        writer = pd.ExcelWriter(output_path, engine='openpyxl')
        
        # 1. 项目摘要表
        summary_data = {
            '项目信息': ['项目名称', '项目描述', '创建日期', '最后更新日期', '发票总数', '总金额', '平均金额', '导出日期'],
            '内容': [
                project_data.get('name', ''),
                project_data.get('description', ''),
                project_data.get('created_at', '').strftime('%Y-%m-%d') if project_data.get('created_at') else '',
                project_data.get('updated_at', '').strftime('%Y-%m-%d') if project_data.get('updated_at') else '',
                len(invoices),
                sum(float(inv.get_total_amount_decimal()) for inv in invoices) if invoices else 0,
                sum(float(inv.get_total_amount_decimal()) for inv in invoices) / len(invoices) if invoices else 0,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='项目摘要', index=False)
        
        # 2. 发票列表表
        if invoices:
            invoice_list_data = []
            
            # 按月统计数据
            monthly_stats = {}
            invoice_type_stats = {}
            seller_stats = {}
            buyer_stats = {}
            
            for invoice in invoices:
                # 发票列表数据
                invoice_data = {
                    '发票代码': invoice.invoice_code,
                    '发票号码': invoice.invoice_number,
                    '发票ID': invoice.combined_id,
                    '发票类型': invoice.invoice_type,
                    '开票日期': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                    '销售方': invoice.seller_name,
                    '销售方税号': invoice.seller_tax_id,
                    '购买方': invoice.buyer_name,
                    '购买方税号': invoice.buyer_tax_id,
                    '金额': invoice.total_amount,
                    '税额': invoice.total_tax,
                    '价税合计': invoice.amount_in_figures,
                    '项目数量': len(invoice.items) if hasattr(invoice, 'items') else 0,
                    '创建时间': invoice.created_at.strftime('%Y-%m-%d %H:%M:%S') if invoice.created_at else ''
                }
                invoice_list_data.append(invoice_data)
                
                # 收集按月统计
                if invoice.invoice_date:
                    month_key = invoice.invoice_date.strftime('%Y-%m')
                    if month_key not in monthly_stats:
                        monthly_stats[month_key] = {'count': 0, 'amount': 0}
                    monthly_stats[month_key]['count'] += 1
                    try:
                        amount = float(invoice.get_total_amount_decimal())
                        monthly_stats[month_key]['amount'] += amount
                    except:
                        pass
                
                # 按发票类型统计
                if invoice.invoice_type:
                    type_key = invoice.invoice_type
                    if type_key not in invoice_type_stats:
                        invoice_type_stats[type_key] = {'count': 0, 'amount': 0}
                    invoice_type_stats[type_key]['count'] += 1
                    try:
                        amount = float(invoice.get_total_amount_decimal())
                        invoice_type_stats[type_key]['amount'] += amount
                    except:
                        pass
                
                # 按销售方统计
                if invoice.seller_name:
                    if invoice.seller_name not in seller_stats:
                        seller_stats[invoice.seller_name] = {'count': 0, 'amount': 0}
                    seller_stats[invoice.seller_name]['count'] += 1
                    try:
                        amount = float(invoice.get_total_amount_decimal())
                        seller_stats[invoice.seller_name]['amount'] += amount
                    except:
                        pass
                
                # 按购买方统计
                if invoice.buyer_name:
                    if invoice.buyer_name not in buyer_stats:
                        buyer_stats[invoice.buyer_name] = {'count': 0, 'amount': 0}
                    buyer_stats[invoice.buyer_name]['count'] += 1
                    try:
                        amount = float(invoice.get_total_amount_decimal())
                        buyer_stats[invoice.buyer_name]['amount'] += amount
                    except:
                        pass
            
            # 写入发票列表
            invoice_list_df = pd.DataFrame(invoice_list_data)
            invoice_list_df.to_excel(writer, sheet_name='发票列表', index=False)
            
            # 3. 商品明细表
            items_data = []
            for invoice in invoices:
                if hasattr(invoice, 'items') and invoice.items:
                    for item in invoice.items:
                        item_data = {
                            '发票ID': invoice.combined_id,
                            '发票号码': invoice.invoice_number,
                            '开票日期': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                            '商品名称': item.name,
                            '规格型号': item.specification,
                            '单位': item.unit,
                            '数量': item.quantity,
                            '单价': item.price,
                            '金额': item.amount,
                            '税率': item.tax_rate,
                            '税额': item.tax
                        }
                        items_data.append(item_data)
            
            if items_data:
                items_df = pd.DataFrame(items_data)
                items_df.to_excel(writer, sheet_name='商品明细', index=False)
                
            # 新增：每张发票的详细工作表
            for idx, invoice in enumerate(invoices):
                if hasattr(invoice, 'formatted_data') and invoice.formatted_data:
                    # 只为前10张发票创建单独的工作表，避免工作表过多
                    if idx >= 10:
                        break
                        
                    # 创建工作表名称 (最多31个字符)
                    sheet_name = f"发票{idx+1}_{invoice.invoice_number[-6:] if invoice.invoice_number else ''}"
                    sheet_name = sheet_name[:31]  # Excel工作表名称限制
                    
                    # 基本信息
                    basic_info = invoice.formatted_data.get('基本信息', {})
                    seller_info = invoice.formatted_data.get('销售方信息', {})
                    buyer_info = invoice.formatted_data.get('购买方信息', {})
                    amount_info = invoice.formatted_data.get('金额信息', {})
                    other_info = invoice.formatted_data.get('其他信息', {})
                    
                    # 基本发票信息表
                    basic_df = pd.DataFrame({
                        '项目': [
                            '发票类型', '发票代码', '发票号码', '开票日期', '校验码', '机器编号',
                            '销售方名称', '销售方识别号', '销售方地址电话', '销售方开户行及账号',
                            '购买方名称', '购买方识别号', '购买方地址电话', '购买方开户行及账号',
                            '合计金额', '合计税额', '价税合计(大写)', '价税合计(小写)',
                            '备注', '收款人', '复核', '开票人'
                        ],
                        '内容': [
                            basic_info.get('发票类型', ''),
                            basic_info.get('发票代码', ''),
                            basic_info.get('发票号码', ''),
                            basic_info.get('开票日期', ''),
                            basic_info.get('校验码', ''),
                            basic_info.get('机器编号', ''),
                            seller_info.get('名称', ''),
                            seller_info.get('识别号', ''),
                            seller_info.get('地址电话', ''),
                            seller_info.get('开户行及账号', ''),
                            buyer_info.get('名称', ''),
                            buyer_info.get('识别号', ''),
                            buyer_info.get('地址电话', ''),
                            buyer_info.get('开户行及账号', ''),
                            amount_info.get('合计金额', ''),
                            amount_info.get('合计税额', ''),
                            amount_info.get('价税合计(大写)', ''),
                            amount_info.get('价税合计(小写)', ''),
                            other_info.get('备注', ''),
                            other_info.get('收款人', ''),
                            other_info.get('复核', ''),
                            other_info.get('开票人', '')
                        ]
                    })
                    
                    # 写入发票基本信息
                    basic_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
                    
                    # 商品信息，如果有
                    items = invoice.formatted_data.get('商品信息', [])
                    if items:
                        # 处理商品明细信息
                        items_data = []
                        for item in items:
                            items_data.append({
                                '商品名称': item.get('Name', ''),
                                '规格型号': item.get('Specification', ''),
                                '单位': item.get('Unit', ''),
                                '数量': item.get('Quantity', ''),
                                '单价': item.get('Price', ''),
                                '金额': item.get('Amount', ''),
                                '税率': item.get('TaxRate', ''),
                                '税额': item.get('Tax', '')
                            })
                        if items_data:
                            items_df = pd.DataFrame(items_data)
                            # 写入商品明细，从第25行开始
                            items_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=25)
            
            # 4. 按月统计表
            if monthly_stats:
                monthly_data = []
                for month, stats in sorted(monthly_stats.items()):
                    monthly_data.append({
                        '月份': month,
                        '发票数量': stats['count'],
                        '总金额': stats['amount']
                    })
                monthly_df = pd.DataFrame(monthly_data)
                monthly_df.to_excel(writer, sheet_name='按月统计', index=False)
            
            # 5. 按类型统计表
            if invoice_type_stats:
                type_data = []
                for type_name, stats in invoice_type_stats.items():
                    type_data.append({
                        '发票类型': type_name,
                        '发票数量': stats['count'],
                        '总金额': stats['amount'],
                        '平均金额': stats['amount'] / stats['count'] if stats['count'] > 0 else 0
                    })
                type_df = pd.DataFrame(type_data)
                type_df.to_excel(writer, sheet_name='发票类型分析', index=False)
            
            # 6. 交易方分析
            # 销售方分析
            if seller_stats:
                seller_data = []
                for seller, stats in sorted(seller_stats.items(), key=lambda x: x[1]['amount'], reverse=True):
                    seller_data.append({
                        '销售方': seller,
                        '交易次数': stats['count'],
                        '总金额': stats['amount'],
                        '平均金额': stats['amount'] / stats['count'] if stats['count'] > 0 else 0
                    })
                seller_df = pd.DataFrame(seller_data)
                seller_df.to_excel(writer, sheet_name='销售方分析', index=False)
            
            # 购买方分析
            if buyer_stats:
                buyer_data = []
                for buyer, stats in sorted(buyer_stats.items(), key=lambda x: x[1]['amount'], reverse=True):
                    buyer_data.append({
                        '购买方': buyer,
                        '交易次数': stats['count'],
                        '总金额': stats['amount'],
                        '平均金额': stats['amount'] / stats['count'] if stats['count'] > 0 else 0
                    })
                buyer_df = pd.DataFrame(buyer_data)
                buyer_df.to_excel(writer, sheet_name='购买方分析', index=False)
        
        # 保存Excel文件
        writer.close()
        
        return output_path


# 兼容旧代码的函数
def export_to_csv(invoice_data, output_path=None):
    """为了兼容旧代码，提供与类相同的静态方法"""
    return InvoiceExporter.export_to_csv(invoice_data, output_path)

def export_to_excel(invoice_data, output_path=None):
    """为了兼容旧代码，提供与类相同的静态方法"""
    return InvoiceExporter.export_to_excel(invoice_data, output_path)

def export_project_to_excel(project_data, invoices, output_path=None):
    """为了兼容旧代码，提供项目导出函数"""
    return InvoiceExporter.export_project_to_excel(project_data, invoices, output_path)

def process_json_to_exports(json_file, formats=None):
    """为了兼容旧代码，提供与类相同的静态方法"""
    return InvoiceExporter.process_json_to_exports(json_file, formats)


# 命令行入口点
def main():
    """主函数，处理命令行参数并调用相应功能"""
    import argparse
    
    parser = argparse.ArgumentParser(description='将发票JSON数据导出为其他格式')
    parser.add_argument('json_file', help='JSON文件路径')
    parser.add_argument('--formats', '-f', nargs='+', choices=['csv', 'excel'], 
                        default=['csv'], help='导出格式，可选值：csv, excel，默认为csv')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.json_file):
        print(f"错误: 文件 '{args.json_file}' 不存在!")
        sys.exit(1)
    
    process_json_to_exports(args.json_file, args.formats)

if __name__ == "__main__":
    main() 
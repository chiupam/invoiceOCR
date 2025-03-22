#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
脚本名称: generate_test_data.py
用途: 生成测试用的发票数据
创建日期: 2023-03-22
"""

import argparse
import datetime
import os
import sys
import random
import logging
import json
from decimal import Decimal

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('generate_test_data')

# 项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 添加项目根目录到路径
sys.path.insert(0, BASE_DIR)

# 公司名称样本
COMPANY_NAMES = [
    "湖南航天建筑工程有限公司",
    "长沙高新技术开发区管理委员会",
    "湖南省人民医院",
    "湖南大学",
    "湖南泽联经贸有限公司",
    "中国电信股份有限公司湖南分公司",
    "湖南国际金融中心",
    "长沙市政府采购中心",
    "湖南省财政厅",
    "湖南创新设计院有限公司"
]

# 商品名称样本
PRODUCT_NAMES = [
    "办公用品",
    "电脑设备",
    "软件服务",
    "会议服务",
    "差旅费",
    "餐饮费",
    "培训费",
    "印刷费",
    "通讯费",
    "咨询服务"
]

# 发票类型
INVOICE_TYPES = [
    "增值税专用发票",
    "增值税普通发票",
    "电子发票(普通发票)"
]

def generate_random_date(start_date, end_date):
    """生成指定范围内的随机日期"""
    time_delta = end_date - start_date
    days_delta = time_delta.days
    random_days = random.randint(0, days_delta)
    return start_date + datetime.timedelta(days=random_days)

def generate_random_amount():
    """生成随机金额"""
    # 生成1000-50000之间的随机金额
    amount = round(random.uniform(1000, 50000), 2)
    return amount

def generate_tax_amount(amount, tax_rate):
    """根据金额和税率计算税额"""
    tax_amount = round(amount * tax_rate, 2)
    return tax_amount

def generate_random_invoice_code():
    """生成随机发票代码"""
    # 生成10位数字的发票代码
    return ''.join([str(random.randint(0, 9)) for _ in range(10)])

def generate_random_invoice_number():
    """生成随机发票号码"""
    # 生成8位数字的发票号码
    return ''.join([str(random.randint(0, 9)) for _ in range(8)])

def format_amount(amount):
    """格式化金额，保留两位小数"""
    return f"¥{amount:.2f}"

def generate_item_data(count=1):
    """生成商品项目数据"""
    items = []
    for i in range(count):
        # 随机商品名称
        name = random.choice(PRODUCT_NAMES)
        # 随机单价 (100-1000元)
        unit_price = round(random.uniform(100, 1000), 2)
        # 随机数量 (1-10)
        quantity = random.randint(1, 10)
        # 计算金额
        amount_without_tax = round(unit_price * quantity, 2)
        # 税率 (3%-17%)
        tax_rate = random.choice([0.03, 0.06, 0.09, 0.13, 0.17])
        # 计算税额
        tax_amount = round(amount_without_tax * tax_rate, 2)
        
        item = {
            "AmountWithoutTax": str(amount_without_tax),
            "LineNo": str(i),
            "Name": f"*{name}*",
            "Quantity": str(quantity),
            "Spec": "",
            "TaxAmount": str(tax_amount),
            "TaxRate": f"{int(tax_rate * 100)}%",
            "Unit": "个",
            "UnitPrice": str(unit_price)
        }
        items.append(item)
    
    return items

def generate_vat_invoice_info(is_special=True):
    """生成增值税发票信息"""
    # 生成随机日期 (过去半年内)
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=180)
    invoice_date = generate_random_date(start_date, today)
    date_str = invoice_date.strftime("%Y年%m月%d日")
    
    # 生成随机发票代码和号码
    invoice_code = generate_random_invoice_code()
    invoice_number = generate_random_invoice_number()
    
    # 随机选择公司名称
    seller_name = random.choice(COMPANY_NAMES)
    buyer_name = random.choice([name for name in COMPANY_NAMES if name != seller_name])
    
    # 生成随机税号 (18位数字和字母组合)
    def generate_tax_id():
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return ''.join(random.choice(chars) for _ in range(18))
    
    seller_tax_id = generate_tax_id()
    buyer_tax_id = generate_tax_id()
    
    # 生成随机商品项目 (1-5个)
    item_count = random.randint(1, 5)
    items = generate_item_data(item_count)
    
    # 计算总金额和总税额
    total_amount = sum(float(item["AmountWithoutTax"]) for item in items)
    total_tax = sum(float(item["TaxAmount"]) for item in items)
    total_amount_with_tax = total_amount + total_tax
    
    # 生成大写金额
    def amount_to_chinese(amount):
        chinese_nums = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
        chinese_units = ['', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿']
        chinese_decimal = ['角', '分']
        
        # 分离整数和小数部分
        int_amount = int(amount)
        decimal_amount = int(round((amount - int_amount) * 100))
        
        result = ""
        
        # 处理整数部分
        if int_amount == 0:
            result = "零"
        else:
            int_str = str(int_amount)
            for i, digit in enumerate(int_str):
                pos = len(int_str) - i - 1
                result += chinese_nums[int(digit)] + (chinese_units[pos] if int(digit) != 0 else "")
        
        result += "圆"
        
        # 处理小数部分
        if decimal_amount > 0:
            decimal_str = f"{decimal_amount:02d}"
            for i, digit in enumerate(decimal_str):
                if int(digit) > 0:
                    result += chinese_nums[int(digit)] + chinese_decimal[i]
        
        return result
    
    amount_in_words = amount_to_chinese(total_amount_with_tax)
    
    # 确定发票类型
    invoice_type = "增值税专用发票" if is_special else random.choice(["增值税普通发票", "电子发票(普通发票)"])
    
    # 构建发票信息列表
    vat_invoice_infos = [
        {"Name": "发票类型", "Value": invoice_type},
        {"Name": "发票代码", "Value": invoice_code},
        {"Name": "发票号码", "Value": invoice_number},
        {"Name": "开票日期", "Value": date_str},
        {"Name": "购买方名称", "Value": buyer_name},
        {"Name": "购买方识别号", "Value": buyer_tax_id},
        {"Name": "销售方名称", "Value": seller_name},
        {"Name": "销售方识别号", "Value": seller_tax_id},
        {"Name": "合计金额", "Value": f"¥{total_amount:.2f}"},
        {"Name": "合计税额", "Value": f"¥{total_tax:.2f}"},
        {"Name": "价税合计(大写)", "Value": amount_in_words},
        {"Name": "价税合计(小写)", "Value": f"¥{total_amount_with_tax:.2f}"}
    ]
    
    # 构建完整响应
    response = {
        "Response": {
            "Angle": 0,
            "Items": items,
            "VatInvoiceInfos": vat_invoice_infos
        }
    }
    
    return response

def save_test_data(data, output_dir, is_special=True):
    """保存测试数据到文件"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"创建输出目录: {output_dir}")
    
    # 获取发票信息
    invoice_type = "专票" if is_special else "普票"
    invoice_code = ""
    invoice_number = ""
    
    for item in data["Response"]["VatInvoiceInfos"]:
        if item["Name"] == "发票代码":
            invoice_code = item["Value"]
        elif item["Name"] == "发票号码":
            invoice_number = item["Value"]
    
    # 生成文件名
    filename = f"{invoice_code}_{invoice_number}_{invoice_type}.json"
    file_path = os.path.join(output_dir, filename)
    
    # 保存到文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"生成测试数据: {file_path}")
    
    return file_path

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='发票测试数据生成工具')
    parser.add_argument('count', type=int, nargs='?', default=5, help='生成的测试数据数量, 默认为5')
    parser.add_argument('--output', default=os.path.join(BASE_DIR, 'test', 'fixtures', 'invoices'), help='输出目录')
    parser.add_argument('--type', choices=['all', 'special', 'normal'], default='all', help='生成的发票类型: all=两种类型, special=专票, normal=普票')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    # 生成测试数据
    generated_files = []
    
    for i in range(args.count):
        # 确定要生成的发票类型
        if args.type == 'all':
            is_special = random.choice([True, False])
        elif args.type == 'special':
            is_special = True
        else:  # normal
            is_special = False
        
        # 生成数据
        data = generate_vat_invoice_info(is_special)
        
        # 保存数据
        file_path = save_test_data(data, args.output, is_special)
        generated_files.append(file_path)
    
    logger.info(f"成功生成 {len(generated_files)} 个测试数据文件")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 
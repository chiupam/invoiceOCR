#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import datetime

class InvoiceFormatter:
    """发票数据格式化工具类"""
    
    @staticmethod
    def format_invoice_data(json_file=None, json_string=None):
        """
        将OCR识别的发票数据格式化为更直观的结构
        
        参数:
            json_file: JSON文件路径
            json_string: JSON字符串
        
        返回:
            格式化后的发票数据字典
        """
        # 加载JSON数据
        if json_file:
            with open(json_file, 'r', encoding='utf-8') as f:
                response_json = json.load(f)
        elif json_string:
            response_json = json.loads(json_string)
        else:
            raise ValueError("需要提供JSON文件路径或JSON字符串")
        
        # 提取并整理发票信息
        if "Response" in response_json and "VatInvoiceInfos" in response_json["Response"]:
            invoice_data = {}
            # 构建查找表
            for item in response_json["Response"]["VatInvoiceInfos"]:
                if "Name" in item and "Value" in item:
                    invoice_data[item["Name"]] = item["Value"]
            
            # 商品项目信息
            items_info = []
            if "Items" in response_json["Response"]:
                items_info = response_json["Response"]["Items"]
            
            # 整理为结构化数据
            formatted_invoice = {
                "基本信息": {
                    "发票类型": invoice_data.get("发票类型", ""),
                    "发票代码": invoice_data.get("发票代码", ""),
                    "发票号码": InvoiceFormatter.format_invoice_number(invoice_data.get("发票号码", "")),
                    "开票日期": invoice_data.get("开票日期", ""),
                    "校验码": invoice_data.get("校验码", ""),
                    "机器编号": invoice_data.get("机器编号", "")
                },
                "销售方信息": {
                    "名称": invoice_data.get("销售方名称", ""),
                    "识别号": invoice_data.get("销售方识别号", ""),
                    "地址电话": invoice_data.get("销售方地址、电话", ""),
                    "开户行及账号": invoice_data.get("销售方开户行及账号", "")
                },
                "购买方信息": {
                    "名称": invoice_data.get("购买方名称", ""),
                    "识别号": invoice_data.get("购买方识别号", ""),
                    "地址电话": invoice_data.get("购买方地址、电话", ""),
                    "开户行及账号": invoice_data.get("购买方开户行及账号", "")
                },
                "金额信息": {
                    "合计金额": InvoiceFormatter.format_amount(invoice_data.get("合计金额", "")),
                    "合计税额": InvoiceFormatter.format_amount(invoice_data.get("合计税额", "")),
                    "价税合计(大写)": invoice_data.get("价税合计(大写)", ""),
                    "价税合计(小写)": InvoiceFormatter.format_amount(invoice_data.get("小写金额", ""))
                },
                "商品信息": items_info,
                "其他信息": {
                    "备注": invoice_data.get("备注", ""),
                    "收款人": invoice_data.get("收款人", ""),
                    "复核": invoice_data.get("复核", ""),
                    "开票人": invoice_data.get("开票人", "")
                },
                "处理时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 标准化日期格式，便于排序
            try:
                invoice_date = invoice_data.get("开票日期", "")
                if invoice_date:
                    # 处理常见的日期格式，例如 "2023年03月15日" 或 "2023-03-15"
                    if "年" in invoice_date and "月" in invoice_date and "日" in invoice_date:
                        date_parts = []
                        for part in ["年", "月", "日"]:
                            idx = invoice_date.find(part)
                            if idx > 0:
                                start_idx = 0 if not date_parts else invoice_date.find(date_parts[-1]) + len(date_parts[-1])
                                date_parts.append(invoice_date[start_idx:idx+1])
                        
                        year = date_parts[0].replace("年", "")
                        month = date_parts[1].replace("月", "")
                        day = date_parts[2].replace("日", "")
                        
                        # 确保年份是4位数
                        if len(year) == 2:
                            year = "20" + year
                            
                        # 确保月和日是两位数
                        month = month.zfill(2)
                        day = day.zfill(2)
                        
                        formatted_date = f"{year}-{month}-{day}"
                    else:
                        # 尝试处理其他格式
                        date_separators = ['-', '/', '.']
                        for sep in date_separators:
                            if sep in invoice_date:
                                date_parts = invoice_date.split(sep)
                                if len(date_parts) >= 3:
                                    year = date_parts[0]
                                    month = date_parts[1].zfill(2)
                                    day = date_parts[2].zfill(2)
                                    formatted_date = f"{year}-{month}-{day}"
                                    break
                        else:
                            formatted_date = invoice_date
                    
                    formatted_invoice["基本信息"]["开票日期标准格式"] = formatted_date
            except Exception:
                # 如果日期格式化失败，保留原始格式
                formatted_invoice["基本信息"]["开票日期标准格式"] = invoice_data.get("开票日期", "")
            
            return formatted_invoice
        else:
            return {"error": "无法找到有效的发票数据"}

    @staticmethod
    def format_invoice_number(number):
        """
        格式化发票号码，去除No或No.前缀
        
        参数:
            number: 原始发票号码
            
        返回:
            格式化后的发票号码（仅数字部分）
        """
        if not number:
            return ""
            
        # 去除No或No.前缀
        if number.startswith("No."):
            return number[3:]
        elif number.startswith("No"):
            return number[2:]
        return number
        
    @staticmethod
    def format_amount(amount):
        """
        格式化金额，去除重复的货币符号
        
        参数:
            amount: 原始金额字符串
            
        返回:
            格式化后的金额字符串
        """
        if not amount:
            return ""
            
        # 移除所有¥和￥符号
        amount = amount.replace("¥", "").replace("￥", "").strip()
        
        # 仅添加一个¥符号
        return f"¥{amount}"


# 兼容旧代码的函数
def format_invoice_data(json_file=None, json_string=None):
    """为了兼容旧代码，提供与类相同的静态方法"""
    return InvoiceFormatter.format_invoice_data(json_file, json_string)


# 命令行入口点
def main():
    # 从命令行参数读取JSON文件
    if len(sys.argv) < 2:
        print("使用方法: python invoice_formatter.py <json_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    try:
        formatted_data = format_invoice_data(json_file=json_file)
        print(json.dumps(formatted_data, ensure_ascii=False, indent=4))
    except Exception as e:
        print(f"处理发票数据时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
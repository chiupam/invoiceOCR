#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        logger.info(f"开始格式化发票数据: {json_file or '从字符串'}")
        
        # 提取并整理发票信息
        if "Response" in response_json:
            # 检查发票类型标识
            invoice_type = ""
            if "VatInvoiceInfos" in response_json["Response"]:
                for item in response_json["Response"]["VatInvoiceInfos"]:
                    if item.get("Name") in ["发票类型", "发票名称"]:
                        invoice_type = item.get("Value", "")
                        break
            
            logger.info(f"检测到发票类型: {invoice_type}")
            
            # 判断发票类型并格式化
            if "VatInvoiceInfos" in response_json["Response"]:
                if "普通发票" in invoice_type:
                    logger.info("识别为增值税普通发票，使用普通发票格式化")
                    return InvoiceFormatter._format_general_invoice(response_json)
                else:
                    logger.info("识别为增值税专用发票，使用专用发票格式化")
                    return InvoiceFormatter._format_vat_invoice(response_json)
            else:
                logger.warning("未找到VatInvoiceInfos字段，尝试作为普通发票处理")
                return InvoiceFormatter._format_general_invoice(response_json)
        else:
            logger.error("无法找到有效的发票数据")
            return {"error": "无法找到有效的发票数据"}
    
    @staticmethod
    def _format_vat_invoice(response_json):
        """
        格式化增值税专用发票
        """
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
                "发票类型": invoice_data.get("发票类型", "增值税专用发票"),
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
        
        # 标准化日期格式
        InvoiceFormatter._standardize_date(formatted_invoice, invoice_data)
        
        return formatted_invoice
    
    @staticmethod
    def _format_general_invoice(response_json):
        """
        格式化增值税普通发票和其他类型发票
        """
        invoice_data = {}
        
        # 从VatInvoiceInfos中提取数据
        if "VatInvoiceInfos" in response_json["Response"]:
            for item in response_json["Response"]["VatInvoiceInfos"]:
                if "Name" in item and "Value" in item:
                    # 处理可能的字段名差异
                    field_name = item["Name"]
                    # 处理购买方和销售方标识号的不同命名
                    if field_name == "购买方统一社会信用代码/纳税人识别号":
                        invoice_data["购买方识别号"] = item["Value"]
                    elif field_name == "销售方统一社会信用代码/纳税人识别号":
                        invoice_data["销售方识别号"] = item["Value"]
                    else:
                        invoice_data[field_name] = item["Value"]
        
        # 商品项目信息
        items_info = []
        if "Items" in response_json["Response"]:
            items_info = response_json["Response"]["Items"]
        
        # 普通发票可能没有合计金额和合计税额，如果有总金额则用总金额
        if "合计金额" not in invoice_data and "金额" in invoice_data:
            invoice_data["合计金额"] = invoice_data["金额"]
        
        if "小写金额" not in invoice_data:
            # 尝试使用其他可能的字段名
            for field in ["价税合计", "总计金额", "总金额", "金额", "价税合计(小写)"]:
                if field in invoice_data:
                    invoice_data["小写金额"] = invoice_data[field]
                    break
        
        # 确保发票类型正确
        invoice_type = invoice_data.get("发票类型", invoice_data.get("发票名称", ""))
        if not invoice_type:
            invoice_type = "增值税普通发票"  # 默认为增值税普通发票
        
        # 处理普通发票的发票代码
        # 普通发票可能没有单独的发票代码字段，需要从发票号码中提取
        invoice_number = invoice_data.get("发票号码", "")
        invoice_code = invoice_data.get("发票代码", "")
        
        # 如果没有发票代码但有发票号码，尝试从发票号码中提取前10位作为发票代码
        if not invoice_code and invoice_number and len(invoice_number) > 10:
            invoice_code = invoice_number[:10]
            logger.info(f"从发票号码中提取发票代码: {invoice_code}")
            invoice_data["发票代码"] = invoice_code
        
        # 整理为结构化数据
        formatted_invoice = {
            "基本信息": {
                "发票类型": invoice_type,
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
        
        # 标准化日期格式
        InvoiceFormatter._standardize_date(formatted_invoice, invoice_data)
        
        # 打印调试信息
        logger.info(f"普通发票格式化结果 - 发票代码: {formatted_invoice['基本信息']['发票代码']}, 发票号码: {formatted_invoice['基本信息']['发票号码']}")
        
        return formatted_invoice
    
    @staticmethod
    def _standardize_date(formatted_invoice, invoice_data):
        """标准化日期格式，便于排序"""
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
        except Exception as e:
            # 如果日期格式化失败，保留原始格式
            logger.warning(f"日期格式化失败: {e}")
            formatted_invoice["基本信息"]["开票日期标准格式"] = invoice_data.get("开票日期", "")

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
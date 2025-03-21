#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import hmac
import json
import sys
import time
import os
from datetime import datetime
if sys.version_info[0] <= 2:
    from httplib import HTTPSConnection
else:
    from http.client import HTTPSConnection

# 导入环境变量支持
from dotenv import load_dotenv

# 导入发票格式化函数
from invoice_formatter import format_invoice_data
# 导入导出相关函数
from invoice_export import export_to_csv, export_to_excel

# 加载环境变量
load_dotenv()

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def call_ocr_api(image_path=None, image_url=None):
    """
    调用腾讯云增值税发票OCR识别API
    
    参数:
        image_path: 本地图片路径（二选一）
        image_url: 图片URL（二选一）
    
    返回:
        API返回的JSON响应
    """
    # 腾讯云API认证信息 - 从环境变量获取
    secret_id = os.environ.get('TENCENT_SECRET_ID', '')
    secret_key = os.environ.get('TENCENT_SECRET_KEY', '')
    token = ""
    
    # 验证密钥不为空
    if not secret_id or not secret_key:
        raise ValueError("Missing Tencent Cloud API credentials. Please set TENCENT_SECRET_ID and TENCENT_SECRET_KEY environment variables.")

    service = "ocr"
    host = "ocr.tencentcloudapi.com"
    region = "ap-guangzhou"
    version = "2018-11-19"
    action = "VatInvoiceOCR"
    
    # 准备请求内容
    request_data = {}
    
    if image_path:
        with open(image_path, "rb") as f:
            image_content = f.read()
        import base64
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        request_data["ImageBase64"] = image_base64
    elif image_url:
        request_data["ImageUrl"] = image_url
    else:
        raise ValueError("必须提供图片路径或图片URL")
    
    payload = json.dumps(request_data)
    
    # ************* 步骤 1：拼接规范请求串 *************
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')
    
    algorithm = "TC3-HMAC-SHA256"
    ct = "application/json; charset=utf-8"
    canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, host, action.lower())
    signed_headers = "content-type;host;x-tc-action"
    hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (http_request_method + "\n" +
                         canonical_uri + "\n" +
                         canonical_querystring + "\n" +
                         canonical_headers + "\n" +
                         signed_headers + "\n" +
                         hashed_request_payload)

    # ************* 步骤 2：拼接待签名字符串 *************
    credential_scope = date + "/" + service + "/" + "tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = (algorithm + "\n" +
                      str(timestamp) + "\n" +
                      credential_scope + "\n" +
                      hashed_canonical_request)

    # ************* 步骤 3：计算签名 *************
    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # ************* 步骤 4：拼接 Authorization *************
    authorization = (algorithm + " " +
                     "Credential=" + secret_id + "/" + credential_scope + ", " +
                     "SignedHeaders=" + signed_headers + ", " +
                     "Signature=" + signature)

    # ************* 步骤 5：构造并发起请求 *************
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version
    }
    if region:
        headers["X-TC-Region"] = region
    if token:
        headers["X-TC-Token"] = token

    try:
        req = HTTPSConnection(host)
        req.request("POST", "/", headers=headers, body=payload.encode("utf-8"))
        resp = req.getresponse()
        return resp.read().decode("utf-8")
    except Exception as err:
        raise Exception(f"API请求失败: {err}")

def process_invoice_image(image_path=None, image_url=None, output_dir="output", export_formats=None):
    """
    处理发票图片，调用OCR API，解析并保存结果
    
    参数:
        image_path: 本地图片路径
        image_url: 图片URL
        output_dir: 输出目录
        export_formats: 导出格式列表，可选值：'json', 'csv', 'excel'，默认只导出json
    """
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 默认导出格式
    if export_formats is None:
        export_formats = ['json']
    
    try:
        # 调用OCR API
        response_data = call_ocr_api(image_path, image_url)
        
        # 生成时间戳用于文件名
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存原始API响应
        raw_output_path = os.path.join(output_dir, f"raw_response_{timestamp_str}.json")
        with open(raw_output_path, "w", encoding="utf-8") as f:
            f.write(response_data)
        print(f"原始API响应已保存到: {raw_output_path}")
        
        # 格式化发票数据并保存
        formatted_data = format_invoice_data(json_string=response_data)
        
        # 导出为指定格式
        if 'json' in export_formats:
            formatted_output_path = os.path.join(output_dir, f"formatted_invoice_{timestamp_str}.json")
            with open(formatted_output_path, "w", encoding="utf-8") as f:
                json.dump(formatted_data, f, ensure_ascii=False, indent=4)
            print(f"格式化后的发票数据已保存为JSON: {formatted_output_path}")
        
        if 'csv' in export_formats:
            csv_path = export_to_csv(formatted_data, os.path.join(output_dir, f"invoice_{timestamp_str}.csv"))
            print(f"发票数据已导出为CSV: {csv_path}")
        
        if 'excel' in export_formats:
            excel_path = export_to_excel(formatted_data, os.path.join(output_dir, f"invoice_{timestamp_str}.xlsx"))
            if excel_path:
                print(f"发票数据已导出为Excel: {excel_path}")
        
        # 输出发票基本信息摘要
        print("\n发票基本信息:")
        print(f"发票类型: {formatted_data['基本信息']['发票类型']}")
        print(f"发票代码: {formatted_data['基本信息']['发票代码']}")
        print(f"发票号码: {formatted_data['基本信息']['发票号码']}")
        print(f"开票日期: {formatted_data['基本信息']['开票日期']}")
        print(f"价税合计: {formatted_data['金额信息']['价税合计(小写)']}")
        
        return formatted_data
    
    except Exception as e:
        print(f"处理发票图片时出错: {e}")
        return None

def main():
    """主函数，处理命令行参数并调用相应功能"""
    import argparse
    
    parser = argparse.ArgumentParser(description='处理发票图片并识别内容')
    parser.add_argument('input_path', help='发票图片路径或URL')
    parser.add_argument('--output-dir', '-o', default='output', help='输出目录，默认为"output"')
    parser.add_argument('--formats', '-f', nargs='+', choices=['json', 'csv', 'excel'], 
                        default=['json'], help='导出格式，可选值：json, csv, excel，默认为json')
    
    args = parser.parse_args()
    
    # 判断输入是本地文件还是URL
    if args.input_path.startswith(('http://', 'https://')):
        process_invoice_image(image_url=args.input_path, output_dir=args.output_dir, export_formats=args.formats)
    else:
        # 检查文件是否存在
        if not os.path.exists(args.input_path):
            print(f"错误: 文件 '{args.input_path}' 不存在!")
            sys.exit(1)
        process_invoice_image(image_path=args.input_path, output_dir=args.output_dir, export_formats=args.formats)

if __name__ == "__main__":
    main() 
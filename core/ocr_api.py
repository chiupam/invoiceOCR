#!/usr/bin/env python
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import sys
import time
import base64
import os
from datetime import datetime, timezone

# 添加项目根目录到Python路径，以便能够正确导入app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ocr.v20181119 import ocr_client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

if sys.version_info[0] <= 2:
    from httplib import HTTPSConnection
else:
    from http.client import HTTPSConnection


def sign(key, msg):
    """用于API鉴权的签名"""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_api_credentials():
    """获取API凭证，优先从环境变量获取"""
    # 直接从环境变量获取
    secret_id = os.environ.get('TENCENT_SECRET_ID')
    secret_key = os.environ.get('TENCENT_SECRET_KEY')
    
    # 如果在Flask应用中，尝试从数据库获取
    try:
        from flask import current_app
        if current_app:
            from app.models import Settings
            if not secret_id:
                secret_id = Settings.get_value('TENCENT_SECRET_ID')
            if not secret_key:
                secret_key = Settings.get_value('TENCENT_SECRET_KEY')
    except (ImportError, RuntimeError):
        # 不在Flask应用上下文中，继续使用环境变量
        pass
    
    return secret_id, secret_key


class OCRClient:
    """腾讯云OCR API客户端"""
    
    def __init__(self):
        # 获取API凭证
        secret_id, secret_key = get_api_credentials()
        
        if not secret_id or not secret_key:
            raise ValueError('未找到腾讯云API密钥，请确保设置了环境变量TENCENT_SECRET_ID和TENCENT_SECRET_KEY，或在系统设置中配置')
        
        # 实例化一个认证对象
        self.cred = credential.Credential(secret_id, secret_key)
        
        # 实例化一个http选项
        self.httpProfile = HttpProfile()
        self.httpProfile.endpoint = "ocr.tencentcloudapi.com"
        
        # 实例化一个client选项
        self.clientProfile = ClientProfile()
        self.clientProfile.httpProfile = self.httpProfile
        
        # 实例化OCR的client对象
        self.client = ocr_client.OcrClient(self.cred, "ap-guangzhou", self.clientProfile)
        
    def recognize_vat_invoice(self, image_path=None, image_url=None, image_base64=None):
        """
        识别增值税发票
        
        参数:
            image_path: 图片/PDF本地路径
            image_url: 图片/PDF的URL
            image_base64: 图片/PDF的Base64编码
            
        返回:
            API返回的JSON结果
        """
        # 设置操作类型
        action = "VatInvoiceOCR"
        
        # 准备请求数据
        request_data = {}
        # 启用PDF识别，指定识别第一页
        request_data["IsPdf"] = True
        request_data["PdfPageNumber"] = 1
        
        # 获取图片数据
        if image_path:
            with open(image_path, "rb") as f:
                image_content = f.read()
            image_base64 = base64.b64encode(image_content).decode('utf-8')
            
        if image_base64:
            request_data["ImageBase64"] = image_base64
        elif image_url:
            request_data["ImageUrl"] = image_url
        else:
            raise ValueError("必须提供图片路径、URL或Base64编码")
        
        # 调用API
        return self._call_api(action, request_data)
    
    def _call_api(self, action, request_data, max_retries=3, timeout=30):
        payload = json.dumps(request_data)

        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""

        timestamp = int(time.time())
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d')

        algorithm = "TC3-HMAC-SHA256"
        ct = "application/json; charset=utf-8"
        canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, self.httpProfile.endpoint, action.lower())
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (http_request_method + "\n" +
                             canonical_uri + "\n" +
                             canonical_querystring + "\n" +
                             canonical_headers + "\n" +
                             signed_headers + "\n" +
                             hashed_request_payload)

        credential_scope = date + "/" + "ocr" + "/" + "tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (algorithm + "\n" +
                         "%d" % timestamp + "\n" +
                         credential_scope + "\n" +
                         hashed_canonical_request)

        secret_id = self.cred.secretId
        secret_key = self.cred.secretKey

        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, "ocr")
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (algorithm + " " +
                         "Credential=" + secret_id + "/" + credential_scope + ", " +
                         "SignedHeaders=" + signed_headers + ", " +
                         "Signature=" + signature)

        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.httpProfile.endpoint,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": "2018-11-19"
        }

        last_error = None
        for attempt in range(max_retries):
            conn = None
            try:
                conn = HTTPSConnection(self.httpProfile.endpoint, timeout=timeout)
                conn.request("POST", "/", headers=headers, body=payload.encode("utf-8"))
                resp = conn.getresponse()
                result = resp.read().decode("utf-8")
                return result
            except Exception as err:
                last_error = err
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                continue
            finally:
                if conn:
                    conn.close()

        raise Exception(f"API请求失败(重试{max_retries}次): {last_error}")


# 如果直接运行此脚本
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ocr_api.py <图片文件路径>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"错误: 找不到图片文件 '{image_path}'")
        sys.exit(1)
        
    try:
        # 创建OCR客户端
        client = OCRClient()
        
        # 识别发票
        print(f"开始识别图片: {image_path}")
        result = client.recognize_vat_invoice(image_path=image_path)
        
        # 格式化输出
        print("\n===== 识别结果 =====")
        formatted_json = json.dumps(json.loads(result), ensure_ascii=False, indent=2)
        print(formatted_json)
        
        # 保存结果到JSON文件
        output_file = f"{os.path.splitext(image_path)[0]}_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(formatted_json)
        print(f"\n识别结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"识别过程中出错: {str(e)}")
        sys.exit(1)


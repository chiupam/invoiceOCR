#!/usr/bin/env python
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import sys
import time
import base64
import os
from datetime import datetime
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ocr.v20181119 import ocr_client, models
from dotenv import load_dotenv
from app.models import Settings

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
    """从数据库获取API凭证"""
    secret_id = Settings.get_value('TENCENT_SECRET_ID')
    secret_key = Settings.get_value('TENCENT_SECRET_KEY')
    
    # 如果数据库中没有，尝试从环境变量获取（兼容旧版本）
    if not secret_id:
        secret_id = os.environ.get('TENCENT_SECRET_ID')
    if not secret_key:
        secret_key = os.environ.get('TENCENT_SECRET_KEY')
    
    return secret_id, secret_key


class OCRClient:
    """腾讯云OCR API客户端"""
    
    def __init__(self):
        # 获取API凭证
        secret_id, secret_key = get_api_credentials()
        
        if not secret_id or not secret_key:
            raise ValueError('尚未配置腾讯云API密钥，请先在系统设置中配置')
        
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
            image_path: 图片本地路径
            image_url: 图片URL
            image_base64: 图片Base64编码
            
        返回:
            API返回的JSON结果
        """
        # 设置操作类型
        action = "VatInvoiceOCR"
        
        # 准备请求数据
        request_data = {}
        
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
    
    def _call_api(self, action, request_data):
        """
        调用API通用方法
        
        参数:
            action: API操作类型
            request_data: 请求数据
            
        返回:
            API返回的JSON字符串
        """
        # 将请求数据转为JSON字符串
        payload = json.dumps(request_data)
        
        # ************* 步骤 1：拼接规范请求串 *************
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')
        
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

        # ************* 步骤 2：拼接待签名字符串 *************
        credential_scope = date + "/" + "ocr" + "/" + "tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (algorithm + "\n" +
                          str(timestamp) + "\n" +
                          credential_scope + "\n" +
                          hashed_canonical_request)

        # ************* 步骤 3：计算签名 *************
        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, "ocr")
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
            "Host": self.httpProfile.endpoint,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": "2018-11-19"
        }

        try:
            req = HTTPSConnection(self.httpProfile.endpoint)
            req.request("POST", "/", headers=headers, body=payload.encode("utf-8"))
            resp = req.getresponse()
            return resp.read().decode("utf-8")
        except Exception as err:
            raise Exception(f"API请求失败: {err}")


# 示例用法
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python ocr_api.py <图片路径或URL>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    ocr_api = OCRClient()
    
    # 判断输入是URL还是本地路径
    if input_path.startswith(('http://', 'https://')):
        result = ocr_api.recognize_vat_invoice(image_url=input_path)
    else:
        result = ocr_api.recognize_vat_invoice(image_path=input_path)
    
    print(result)


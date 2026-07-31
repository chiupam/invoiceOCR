#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""腾讯云OCR API client（dispatcher）。

Calls into the ``core.doc_types`` registry to pick the OCR action for a
given document type. The original ``recognize_vat_invoice()`` method is
preserved as a thin alias so v1.4 callers (notably ``app/utils.py``) keep
working without edits.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
from http.client import HTTPSConnection

from dotenv import load_dotenv

from core.doc_types import get as _get_type

# Add project root so ``app.models`` is importable when running this script standalone.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()


def sign(key, msg):
    """用于API鉴权的签名"""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_api_credentials():
    """获取API凭证，优先从环境变量获取"""
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
    """腾讯云OCR API客户端

    Thin wrapper around the Tencent signed-request machinery. All real
    behaviour (which action to call, how to format the request payload)
    lives in the registered DocType instances; this class only does
    transport + signing.
    """

    def __init__(self):
        # 获取API凭证
        secret_id, secret_key = get_api_credentials()

        if not secret_id or not secret_key:
            raise ValueError(
                '未找到腾讯云API密钥，请确保设置了环境变量TENCENT_SECRET_ID和'
                'TENCENT_SECRET_KEY，或在系统设置中配置'
            )

        # 实例化一个认证对象
        self.cred = _make_credential(secret_id, secret_key)

        # 实例化一个http选项
        self.httpProfile = _make_http_profile("ocr.tencentcloudapi.com")

        # 实例化OCR的client对象
        self.client = _make_ocr_client(self.cred, "ap-guangzhou", self.httpProfile)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recognize(
        self,
        image_path: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        doc_type: str = "vat",
    ) -> str:
        """通用识别入口。

        Parameters
        ----------
        image_path / image_url / image_base64:
            发票图片/PDF 的来源（三选一）。
        doc_type:
            Document type id registered in ``core.doc_types``. Defaults to
            ``"vat"`` for backwards compatibility.

        Returns
        -------
        str
            Raw API JSON response as a string (unchanged from v1.4 — the
            formatter expects a string it can ``json.loads``).
        """
        from core.doc_types import all_types as _all_types
        dt = _get_type(doc_type)
        if dt is None:
            raise ValueError(
                f"未注册的 doc_type={doc_type!r}. "
                f"已知类型: {[t.type_id for t in _all_types()]}"
            )

        action = dt.ocr_action
        request_data: dict = dict(dt.ocr_request_extras())

        # 图片/PDF → base64
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

        return self._call_api(action, request_data)

    # ------------------------------------------------------------------
    # Backwards-compatible alias (v1.4 API)
    # ------------------------------------------------------------------

    def recognize_vat_invoice(
        self,
        image_path: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
    ) -> str:
        """v1.4-compatible VAT-only entry point. Equivalent to
        ``recognize(..., doc_type='vat')``. New code should call
        ``recognize()`` directly."""
        return self.recognize(
            image_path=image_path,
            image_url=image_url,
            image_base64=image_base64,
            doc_type="vat",
        )

    # ------------------------------------------------------------------
    # Tencent signed-request transport (unchanged from v1.4)
    # ------------------------------------------------------------------

    def _call_api(self, action, request_data):
        payload = json.dumps(request_data)

        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""

        timestamp = int(time.time())
        date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')

        algorithm = "TC3-HMAC-SHA256"
        ct = "application/json; charset=utf-8"
        canonical_headers = (
            "content-type:%s\nhost:%s\nx-tc-action:%s\n"
            % (ct, self.httpProfile.endpoint, action.lower())
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            http_request_method + "\n" +
            canonical_uri + "\n" +
            canonical_querystring + "\n" +
            canonical_headers + "\n" +
            signed_headers + "\n" +
            hashed_request_payload
        )

        credential_scope = date + "/" + "ocr" + "/" + "tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (
            algorithm + "\n" +
            "%d" % timestamp + "\n" +
            credential_scope + "\n" +
            hashed_canonical_request
        )

        secret_id = self.cred.secretId
        secret_key = self.cred.secretKey

        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, "ocr")
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        authorization = (
            algorithm + " " +
            "Credential=" + secret_id + "/" + credential_scope + ", " +
            "SignedHeaders=" + signed_headers + ", " +
            "Signature=" + signature
        )

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


# ---------------------------------------------------------------------------
# Lazy SDK imports — only attempt when an OCRClient is actually instantiated,
# so unit tests / formatter-only flows don't require tencentcloud-sdk-python.
# ---------------------------------------------------------------------------

def _make_credential(secret_id, secret_key):
    try:
        from tencentcloud.common import credential
        return credential.Credential(secret_id, secret_key)
    except ImportError as e:
        raise ImportError(
            "tencentcloud-sdk-python is required for OCRClient. "
            "Install it via `pip install tencentcloud-sdk-python`. "
            f"(Underlying error: {e})"
        )


def _make_http_profile(endpoint):
    try:
        from tencentcloud.common.profile.http_profile import HttpProfile
    except ImportError as e:
        raise ImportError(
            "tencentcloud-sdk-python is required for OCRClient. "
            f"(Underlying error: {e})"
        )
    p = HttpProfile()
    p.endpoint = endpoint
    return p


def _make_ocr_client(cred, region, http_profile):
    try:
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.ocr.v20181119 import ocr_client
    except ImportError as e:
        raise ImportError(
            "tencentcloud-sdk-python is required for OCRClient. "
            f"(Underlying error: {e})"
        )
    profile = ClientProfile()
    profile.httpProfile = http_profile
    return ocr_client.OcrClient(cred, region, profile)


# ---------------------------------------------------------------------------
# CLI entry point (preserved from v1.4)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ocr_api.py <图片文件路径> [doc_type]")
        sys.exit(1)

    image_path = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) >= 3 else "vat"

    if not os.path.exists(image_path):
        print(f"错误: 找不到图片文件 '{image_path}'")
        sys.exit(1)

    try:
        client = OCRClient()
        result = client.recognize(image_path=image_path, doc_type=doc_type)

        print(f"\n===== 识别结果 (doc_type={doc_type}) =====")
        formatted_json = json.dumps(json.loads(result), ensure_ascii=False, indent=2)
        print(formatted_json)

        output_file = f"{os.path.splitext(image_path)[0]}_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(formatted_json)
        print(f"\n识别结果已保存到: {output_file}")

    except Exception as e:
        print(f"识别过程中出错: {str(e)}")
        sys.exit(1)

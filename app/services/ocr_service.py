"""OCR processing pipeline service.

Framework-free: safe to run from request handlers or background tasks.
Owns its DB session via SessionLocal so it can run outside a request.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime

from ..config import get_config
from ..database import SessionLocal
from ..models import Invoice, InvoiceItem, OcrTask
from core.doc_types import get as _get_doc_type
from core.extractors import get_backend as _get_backend

logger = logging.getLogger("invoiceocr.ocr")


def allowed_file(filename: str) -> bool:
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in get_config().allowed_extensions


def extract_formatted_data(file_path: str, doc_type: str, backend: str) -> dict:
    """local-pdf first (free/instant for text PDFs), then the chosen backend."""
    formatted_data = None

    if file_path.lower().endswith(".pdf"):
        local_pdf = _get_backend("local-pdf")
        if local_pdf is not None and local_pdf.is_available():
            try:
                candidate = local_pdf.extract(file_path, doc_type)
                has_content = bool(
                    (candidate.invoice_code or candidate.invoice_number)
                    and candidate.amount_in_figures
                    and (candidate.buyer_name or candidate.seller_name)
                )
                if has_content:
                    from core.extractors.to_formatted import parsed_to_formatted
                    formatted_data = parsed_to_formatted(candidate)
                    logger.info("本地 pdfplumber 提取成功 (doc_type=%s)", doc_type)
                else:
                    logger.info("本地 pdfplumber 提取不完整, 回退到 OCR")
            except Exception as e:
                logger.warning("本地 pdfplumber 提取失败, 回退到 OCR: %s", e)

    if formatted_data is None:
        if backend == "vllm":
            extractor = _get_backend("vllm")
            if extractor is None or not extractor.is_available():
                raise RuntimeError(
                    "后端 'vllm' 不可用。请检查 VLLM_OCR_ENDPOINT / VLLM_OCR_API_KEY 配置。"
                )
            from core.extractors.to_formatted import parsed_to_formatted
            formatted_data = parsed_to_formatted(extractor.extract(file_path, doc_type))
        else:
            from core.invoice_formatter import InvoiceFormatter
            from core.ocr_api import OCRClient
            response_json = OCRClient().recognize(image_path=file_path, doc_type=doc_type)
            formatted_data = InvoiceFormatter.format_invoice_data(
                json_string=response_json, doc_type=doc_type,
            )

    if formatted_data is None:
        raise RuntimeError("未能提取发票内容。请确认文件是电子PDF（文本型）或选择可用的OCR后端。")
    return formatted_data


def _save_failed_copy(file_path: str) -> None:
    basename = os.path.basename(file_path)
    if basename.startswith("failed_"):
        return
    failed_copy = os.path.join(os.path.dirname(file_path), f"failed_{basename}")
    try:
        shutil.copy2(file_path, failed_copy)
        logger.info("已保存识别失败文件副本: %s", failed_copy)
    except Exception as e:
        logger.error("保存识别失败文件副本时出错: %s", e)


def process_invoice_file(file_path: str, project_id: int | None = None,
                         doc_type: str = "vat", backend: str = "tencent") -> dict:
    """Full pipeline: extract → dedupe → persist. Returns a result dict."""
    logger.info("开始处理文件: %s (doc_type=%s, backend=%s)", file_path, doc_type, backend)
    cfg = get_config()

    try:
        formatted_data = extract_formatted_data(file_path, doc_type, backend)
    except Exception as e:
        logger.error("处理发票文件时出错: %s", e)
        _save_failed_copy(file_path)
        return {"success": False, "message": f"处理发票文件时出错: {e}"}

    basic = formatted_data.get("基本信息", {})
    invoice_code = basic.get("发票代码", "")
    invoice_number = basic.get("发票号码", "")

    if not invoice_number:
        logger.warning("识别失败: 文件 %s 未能识别出发票号码", file_path)
        _save_failed_copy(file_path)
        return {"success": False,
                "message": "未能识别出发票号码，请检查文件清晰度或文件内容是否为有效发票"}

    with SessionLocal() as db:
        # Dedupe by (code, number); 数电发票 has number only.
        q = db.query(Invoice).filter_by(invoice_number=invoice_number)
        if invoice_code:
            q = q.filter_by(invoice_code=invoice_code)
        existing = q.first()
        if existing:
            try:
                os.remove(file_path)
            except OSError:
                pass
            return {"success": True,
                    "message": f"发票已存在 (ID: {existing.id})",
                    "invoice_id": existing.id}

        # Final filename: <code><number>.<ext> (数电: number only)
        ext = os.path.splitext(file_path)[1].lower()
        if not ext:
            try:
                with open(file_path, "rb") as f:
                    ext = ".pdf" if f.read(4) == b"%PDF" else ".jpg"
            except OSError:
                ext = ".jpg"
        new_filename = f"{invoice_code}{invoice_number}{ext}" if invoice_code \
            else f"{invoice_number}{ext}"
        final_path = os.path.join(cfg.upload_folder, new_filename)
        shutil.copy2(file_path, final_path)
        try:
            os.remove(file_path)
        except OSError:
            pass

        # Type-specific sections (医疗/乘车信息) → extra_data blob
        dt = _get_doc_type(doc_type)
        extra_sections = dt.extra_sections(formatted_data) if dt else {}
        extra_data = None
        if extra_sections:
            extra_data = json.dumps(
                {"v": dt.extra_schema_version, "sections": extra_sections},
                ensure_ascii=False,
            )

        invoice_date = None
        date_std = basic.get("开票日期标准格式", "")
        if date_std:
            try:
                invoice_date = datetime.strptime(date_std, "%Y-%m-%d").date()
            except ValueError:
                pass

        seller = formatted_data.get("销售方信息", {})
        buyer = formatted_data.get("购买方信息", {})
        amounts = formatted_data.get("金额信息", {})

        invoice = Invoice(
            invoice_code=invoice_code,
            invoice_number=invoice_number,
            invoice_type=basic.get("发票类型", ""),
            invoice_date=invoice_date,
            seller_name=seller.get("名称", ""),
            seller_tax_id=seller.get("识别号", ""),
            seller_address=seller.get("地址电话", ""),
            seller_bank_info=seller.get("开户行及账号", ""),
            buyer_name=buyer.get("名称", ""),
            buyer_tax_id=buyer.get("识别号", ""),
            buyer_address=buyer.get("地址电话", ""),
            buyer_bank_info=buyer.get("开户行及账号", ""),
            total_amount=amounts.get("合计金额", ""),
            total_tax=amounts.get("合计税额", ""),
            amount_in_words=amounts.get("价税合计(大写)", ""),
            amount_in_figures=amounts.get("价税合计(小写)", ""),
            image_path=new_filename,
            project_id=project_id,
            doc_type=doc_type,
            extra_data=extra_data,
            json_data=json.dumps(formatted_data, ensure_ascii=False),
        )
        db.add(invoice)
        db.flush()

        for item_data in formatted_data.get("商品信息", []):
            db.add(InvoiceItem.from_item_data(invoice.id, item_data))
        db.commit()

        logger.info("保存发票记录: ID=%s, 代码=%s, 号码=%s",
                    invoice.id, invoice_code, invoice_number)
        return {"success": True, "message": "发票识别并保存成功",
                "invoice_id": invoice.id}


# ---------------------------------------------------------------------------
# Async task runner
# ---------------------------------------------------------------------------

def run_ocr_task(task_id: int) -> None:
    """Background-task entry: load task → run pipeline → record outcome."""
    with SessionLocal() as db:
        task = db.get(OcrTask, task_id)
        if task is None or task.status != "pending":
            return
        task.status = "running"
        db.commit()
        file_path, project_id = task.file_path, task.project_id
        doc_type, backend = task.doc_type or "vat", task.backend or "tencent"

    result = process_invoice_file(file_path, project_id, doc_type, backend)

    with SessionLocal() as db:
        task = db.get(OcrTask, task_id)
        if task is None:
            return
        if result.get("success"):
            task.status = "done"
            task.invoice_id = result.get("invoice_id")
        else:
            task.status = "failed"
            task.error = result.get("message", "未知错误")
        db.commit()

"""JSON API routes: statistics, maintenance, async OCR task polling."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_user, verify_csrf
from ..models import Invoice, InvoiceItem, OcrTask, User
from ..services import export_service
from ..services.stats_service import get_invoice_statistics

logger = logging.getLogger("invoiceocr.api")

router = APIRouter(prefix="/api")

TASK_TTL_HOURS = 24


@router.get("/statistics", name="main.api_statistics")
async def api_statistics(user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    return get_invoice_statistics(db.query(Invoice).all())


@router.get("/tasks/{task_id}", name="main.task_status")
async def task_status(task_id: int, user: User = Depends(require_user),
                      db: Session = Depends(get_db)):
    task = db.get(OcrTask, task_id)
    if task is None:
        return {"task_id": task_id, "status": "failed", "error": "任务不存在"}
    return task.to_dict()


@router.post("/update-all-invoices", dependencies=[Depends(verify_csrf)])
async def update_all_invoices(user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    """Re-apply json_data to the fixed columns of every invoice."""
    invoices = db.query(Invoice).filter(Invoice.json_data.isnot(None)).all()
    updated = 0
    for invoice in invoices:
        try:
            data = json.loads(invoice.json_data)
        except (ValueError, TypeError):
            continue
        basic = data.get("基本信息", {})
        seller = data.get("销售方信息", {})
        buyer = data.get("购买方信息", {})
        amounts = data.get("金额信息", {})
        other = data.get("其他信息", {})

        invoice.invoice_type = basic.get("发票类型", invoice.invoice_type)
        invoice.invoice_code = basic.get("发票代码", invoice.invoice_code)
        invoice.invoice_number = basic.get("发票号码", invoice.invoice_number)
        invoice.check_code = basic.get("校验码", invoice.check_code)
        invoice.machine_number = basic.get("机器编号", invoice.machine_number)
        date_std = basic.get("开票日期标准格式", "")
        if date_std:
            try:
                invoice.invoice_date = datetime.strptime(date_std, "%Y-%m-%d").date()
            except ValueError:
                pass
        invoice.invoice_date_raw = basic.get("开票日期", invoice.invoice_date_raw)

        invoice.seller_name = seller.get("名称", invoice.seller_name)
        invoice.seller_tax_id = seller.get("识别号", invoice.seller_tax_id)
        invoice.seller_address = seller.get("地址电话", invoice.seller_address)
        invoice.seller_bank_info = seller.get("开户行及账号", invoice.seller_bank_info)
        invoice.buyer_name = buyer.get("名称", invoice.buyer_name)
        invoice.buyer_tax_id = buyer.get("识别号", invoice.buyer_tax_id)
        invoice.buyer_address = buyer.get("地址电话", invoice.buyer_address)
        invoice.buyer_bank_info = buyer.get("开户行及账号", invoice.buyer_bank_info)
        invoice.total_amount = amounts.get("合计金额", invoice.total_amount)
        invoice.total_tax = amounts.get("合计税额", invoice.total_tax)
        invoice.amount_in_words = amounts.get("价税合计(大写)", invoice.amount_in_words)
        invoice.amount_in_figures = amounts.get("价税合计(小写)", invoice.amount_in_figures)
        invoice.remarks = other.get("备注", invoice.remarks)
        invoice.payee = other.get("收款人", invoice.payee)
        invoice.reviewer = other.get("复核", invoice.reviewer)
        invoice.issuer = other.get("开票人", invoice.issuer)

        items_data = data.get("商品信息", [])
        if not items_data and isinstance(data.get("Response", {}).get("Items"), list):
            items_data = data["Response"]["Items"]
        db.query(InvoiceItem).filter_by(invoice_id=invoice.id).delete()
        for item_data in items_data:
            db.add(InvoiceItem.from_item_data(invoice.id, item_data))
        updated += 1

    db.commit()
    if updated:
        return {"success": True,
                "message": f"成功更新了 {updated} 条发票记录",
                "updated_count": updated}
    return {"success": False, "message": "没有需要更新的发票记录"}


@router.post("/cleanup-exported-files", dependencies=[Depends(verify_csrf)])
async def cleanup_exported_files(user: User = Depends(require_user)):
    deleted = export_service.cleanup_old_exported_files()
    return {"success": True,
            "message": f"成功清理了 {deleted} 个文件",
            "deleted_count": deleted}

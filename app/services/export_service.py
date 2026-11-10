"""Invoice/project export helpers and export-file cleanup."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from ..config import get_config
from ..models import Invoice, InvoiceItem, Project
from core.invoice_export import InvoiceExporter, export_project_to_excel

logger = logging.getLogger("invoiceocr.export")


def export_invoice(db, invoice_id: int, fmt: str) -> str | None:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or not invoice.json_data:
        return None
    data = json.loads(invoice.json_data)
    if fmt == "csv":
        return InvoiceExporter.export_to_csv(data)
    if fmt == "excel":
        return InvoiceExporter.export_to_excel(data)
    return None


def export_project(db, project_id: int) -> str | None:
    project = db.get(Project, project_id)
    if project is None:
        return None
    invoices = db.query(Invoice).filter_by(project_id=project_id).all()
    for inv in invoices:
        inv.items = db.query(InvoiceItem).filter_by(invoice_id=inv.id).all()
        if inv.json_data:
            try:
                inv.formatted_data = json.loads(inv.json_data)
            except (ValueError, TypeError):
                inv.formatted_data = None
    project_data = {
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    return export_project_to_excel(project_data, invoices)


def cleanup_old_exported_files(days: int = 7) -> int:
    """Delete exported files older than ``days`` from the output dir."""
    output_dir = get_config().output_dir
    deleted = 0
    now = datetime.now()
    try:
        for filename in os.listdir(output_dir):
            path = os.path.join(output_dir, filename)
            if not os.path.isfile(path):
                continue
            age_days = (now - datetime.fromtimestamp(os.path.getmtime(path))).days
            if age_days > days:
                os.remove(path)
                deleted += 1
    except OSError as e:
        logger.error("清理过期导出文件时出错: %s", e)
    return deleted

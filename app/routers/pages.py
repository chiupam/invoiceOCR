"""Page routes (the former Flask main blueprint): dashboard, upload,
invoice CRUD, projects, settings. Route names keep the ``main.*`` style so
ported templates resolve url_for() unchanged.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import (APIRouter, BackgroundTasks, Depends, Form, Query,
                     Request, UploadFile)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_config
from ..database import get_db
from ..deps import flash, require_user, verify_csrf
from ..jinja import render
from ..models import Invoice, InvoiceItem, OcrTask, Project, Settings, User
from ..services import export_service
from ..services.ocr_service import (allowed_file, process_invoice_file,
                                    run_ocr_task)
from ..services.stats_service import get_invoice_statistics
from core.doc_types import all_types as _all_doc_types, get as _get_doc_type
from core.extractors import all_backends as _all_backends, get_backend as _get_backend

logger = logging.getLogger("invoiceocr.pages")

router = APIRouter()

PER_PAGE = 10


class Pagination:
    """Minimal stand-in for Flask-SQLAlchemy's paginate() object."""

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, (total + per_page - 1) // per_page)
        self.prev_num = page - 1 if page > 1 else None
        self.next_num = page + 1 if page < self.pages else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


def _is_xhr(request: Request) -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or \
        "application/json" in request.headers.get("accept", "")


def _check_system_setup() -> bool:
    if (Settings.get_value("TENCENT_SECRET_ID") or os.environ.get("TENCENT_SECRET_ID")) and \
       (Settings.get_value("TENCENT_SECRET_KEY") or os.environ.get("TENCENT_SECRET_KEY")):
        return True
    return bool(Settings.get_value("VLLM_OCR_ENDPOINT") or
                os.environ.get("VLLM_OCR_ENDPOINT"))


def _sidebar_projects(db: Session):
    return db.query(Project).order_by(Project.name).all()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/", name="main.index")
@router.get("/index", include_in_schema=False)
async def index(request: Request,
                page: int = Query(1, ge=1),
                sort_by: str = Query("invoice_date"),
                order: str = Query("desc"),
                project_id: int | None = Query(None),
                search: str = Query(""),
                doc_type: str = Query(""),
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    if doc_type and _get_doc_type(doc_type) is None:
        doc_type = ""

    query = db.query(Invoice)
    current_project = None
    current_project_id = None
    if project_id is not None:
        if project_id == 0:
            query = query.filter(Invoice.project_id.is_(None))
            current_project_id = 0
        else:
            query = query.filter(Invoice.project_id == project_id)
            current_project = db.get(Project, project_id)
            current_project_id = project_id

    if search:
        query = query.filter(Invoice.invoice_number.like(f"%{search}%"))
    if doc_type:
        query = query.filter(Invoice.doc_type == doc_type)

    if sort_by in ("amount", "items_count"):
        all_invoices = query.all()
        if sort_by == "amount":
            all_invoices.sort(key=lambda inv: inv.get_total_amount_decimal(),
                              reverse=(order == "desc"))
        else:
            all_invoices.sort(key=lambda inv: len(inv.items),
                              reverse=(order == "desc"))
        total = len(all_invoices)
        start = (page - 1) * PER_PAGE
        invoices = all_invoices[start:start + PER_PAGE]
        pagination = Pagination(invoices, page, PER_PAGE, total)
    else:
        column = {
            "invoice_date": Invoice.invoice_date,
            "invoice_number": Invoice.invoice_number,
            "created_at": Invoice.created_at,
        }.get(sort_by, Invoice.invoice_date)
        query = query.order_by(column.asc() if order == "asc" else column.desc())
        total = query.count()
        invoices = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
        pagination = Pagination(invoices, page, PER_PAGE, total)

    if project_id is None:
        filtered = db.query(Invoice).all()
    elif project_id == 0:
        filtered = db.query(Invoice).filter(Invoice.project_id.is_(None)).all()
    else:
        filtered = db.query(Invoice).filter_by(project_id=project_id).all()
    stats = get_invoice_statistics(filtered)

    return render(request, "index.html", {
        "invoices": invoices,
        "pagination": pagination,
        "projects": _sidebar_projects(db),
        "stats": stats,
        "current_project_id": current_project_id,
        "current_project": current_project,
        "sort_by": sort_by,
        "order": order,
        "search_query": search,
        "doc_type_filter": doc_type,
        "doc_types": _all_doc_types(),
    })


# ---------------------------------------------------------------------------
# Upload (async OCR for XHR, sync fallback for plain form posts)
# ---------------------------------------------------------------------------

@router.get("/upload", name="main.upload")
async def upload_page(request: Request,
                      project_id: int | None = Query(None),
                      user: User = Depends(require_user),
                      db: Session = Depends(get_db)):
    default_project_id = project_id
    if default_project_id is None:
        cookie_pid = request.cookies.get("last_project_id")
        if cookie_pid and cookie_pid.isdigit():
            default_project_id = int(cookie_pid)

    resp = render(request, "upload.html", {
        "projects": _sidebar_projects(db),
        "default_project_id": default_project_id,
        "current_project_id": default_project_id,
        "doc_types": _all_doc_types(),
        "backends": _all_backends(),
    })
    if project_id is not None:
        resp.set_cookie("last_project_id", str(project_id), max_age=365 * 24 * 3600)
    return resp


async def _save_temp_upload(file: UploadFile) -> str | None:
    if not file.filename or not allowed_file(file.filename):
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_name = f"temp_{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"
    tmp_path = os.path.join(get_config().upload_folder, tmp_name)
    content = await file.read()
    max_bytes = get_config().max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        return None
    with open(tmp_path, "wb") as f:
        f.write(content)
    return tmp_path


def _parse_doc_type(raw: str | None) -> str:
    doc_type = (raw or "vat").strip().lower()
    if _get_doc_type(doc_type) is None:
        doc_type = "vat"
    return doc_type


def _parse_backend(raw: str | None) -> str:
    backend = (raw or "tencent").strip().lower()
    if _get_backend(backend) is None:
        backend = "tencent"
    return backend


@router.post("/upload", dependencies=[Depends(verify_csrf)])
async def upload_submit(request: Request,
                        background_tasks: BackgroundTasks,
                        invoice_file: UploadFile | None = None,
                        project_id: str = Form(""),
                        doc_type: str = Form(""),
                        backend: str = Form(""),
                        user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    if invoice_file is None or not invoice_file.filename:
        return _upload_reject(request, "没有选择文件")

    tmp_path = await _save_temp_upload(invoice_file)
    if tmp_path is None:
        return _upload_reject(request, "不支持的文件类型或文件超过大小限制")

    pid = int(project_id) if project_id and project_id.isdigit() else None
    dt = _parse_doc_type(doc_type)
    be = _parse_backend(backend)

    if _is_xhr(request):
        # Async: return immediately, OCR runs in the background.
        task = OcrTask(status="pending", filename=invoice_file.filename,
                       file_path=tmp_path, doc_type=dt, backend=be, project_id=pid)
        db.add(task)
        db.commit()
        background_tasks.add_task(run_ocr_task, task.id)
        return JSONResponse({"success": True, "pending": True,
                             "task_id": task.id}, status_code=202)

    # Plain form post: keep the synchronous flow with flash + redirect.
    result = process_invoice_file(tmp_path, project_id=pid, doc_type=dt, backend=be)
    if result.get("success"):
        flash(request, "发票上传和识别成功")
        return RedirectResponse(f"/invoice/{result['invoice_id']}", status_code=303)
    flash(request, f"发票识别失败: {result.get('message', '未知错误')}", "danger")
    return RedirectResponse("/upload", status_code=303)


def _upload_reject(request: Request, message: str):
    if _is_xhr(request):
        return JSONResponse({"success": False, "message": message},
                            status_code=400)
    flash(request, message, "danger")
    return RedirectResponse("/upload", status_code=303)


@router.post("/quick_upload", name="main.quick_upload",
             dependencies=[Depends(verify_csrf)])
async def quick_upload(request: Request,
                       invoice_file: UploadFile | None = None,
                       project_id: str = Form(""),
                       user: User = Depends(require_user)):
    """Drag-drop quick upload from the dashboard (synchronous, redirects)."""
    if not _check_system_setup():
        flash(request, "请先完成系统设置", "warning")
        return RedirectResponse("/settings", status_code=303)

    if invoice_file is None or not invoice_file.filename:
        flash(request, "未检测到文件", "danger")
        return RedirectResponse("/", status_code=303)

    tmp_path = await _save_temp_upload(invoice_file)
    if tmp_path is None:
        flash(request, "不支持的文件类型", "danger")
        return RedirectResponse("/", status_code=303)

    pid = int(project_id) if project_id and project_id.isdigit() else None
    result = process_invoice_file(tmp_path, project_id=pid)
    if result.get("success"):
        flash(request, "发票识别成功", "success")
        return RedirectResponse(f"/invoice/{result['invoice_id']}", status_code=303)
    flash(request, f"发票识别失败: {result.get('message')}", "danger")
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------------------
# Invoice create (declared BEFORE /invoice/{invoice_id} so the static
# segment wins over the path parameter), then detail / edit / delete.
# ---------------------------------------------------------------------------

@router.get("/invoice/create", name="main.invoice_create")
async def invoice_create_page(request: Request,
                              user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    return render(request, "invoice_create.html", {
        "projects": _sidebar_projects(db),
        "today": datetime.now().strftime("%Y-%m-%d"),
    })


@router.post("/invoice/create", dependencies=[Depends(verify_csrf)])
async def invoice_create_submit(request: Request,
                                user: User = Depends(require_user),
                                db: Session = Depends(get_db)):
    form = await request.form()
    data = {k: v for k, v in form.multi_items()}

    invoice = Invoice()
    _apply_invoice_form(invoice, data, form)
    invoice.image_path = None
    db.add(invoice)
    db.flush()

    items_added = 0
    for item_data in _collect_items(form):
        db.add(InvoiceItem(invoice_id=invoice.id, **item_data))
        items_added += 1

    try:
        db.commit()
        flash(request, f"新发票创建成功，添加了{items_added}个明细项")
        return RedirectResponse(f"/invoice/{invoice.id}", status_code=303)
    except Exception as e:
        db.rollback()
        logger.error("创建发票时出错: %s", e)
        flash(request, f"保存失败: {e}", "danger")
        return RedirectResponse("/invoice/create", status_code=303)


@router.get("/invoice/{invoice_id}", name="main.invoice_detail")
async def invoice_detail(request: Request, invoice_id: int,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return render(request, "errors/404.html", {}, status_code=404)

    items = db.query(InvoiceItem).filter_by(invoice_id=invoice_id).all()

    back_url = "/"
    referer = request.headers.get("referer", "")
    if "index" in referer and any(k in referer for k in ("page=", "project_id=", "sort_by=")):
        back_url = referer

    return render(request, "invoice_detail.html", {
        "invoice": invoice,
        "items": items,
        "projects": _sidebar_projects(db),
        "current_project_id": invoice.project_id,
        "back_url": back_url,
        "extra_sections": invoice.get_extra_sections(),
    })


def _collect_items(form) -> list[dict]:
    """Extract items[i][field] entries from form data (multi-dict)."""
    data: dict[str, str] = {}
    for key, value in form.multi_items():
        data.setdefault(key, value)
    items = []
    for key in data:
        if key.startswith("items[") and key.endswith("][name]"):
            idx = key[6:].split("]")[0]
            name = data.get(f"items[{idx}][name]", "").strip()
            if not name:
                continue
            items.append({
                "name": name,
                "specification": data.get(f"items[{idx}][specification]", ""),
                "unit": data.get(f"items[{idx}][unit]", ""),
                "quantity": data.get(f"items[{idx}][quantity]", ""),
                "price": data.get(f"items[{idx}][price]", ""),
                "amount": data.get(f"items[{idx}][amount]", ""),
                "tax_rate": data.get(f"items[{idx}][tax_rate]", ""),
                "tax": data.get(f"items[{idx}][tax]", ""),
            })
    return items


def _apply_invoice_form(invoice: Invoice, data: dict, form) -> None:
    invoice.invoice_type = data.get("invoice_type", "")
    invoice.invoice_code = data.get("invoice_code", "")
    invoice.invoice_number = data.get("invoice_number", "")

    date_str = data.get("invoice_date", "")
    if date_str:
        try:
            invoice.invoice_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            invoice.invoice_date_raw = date_str
        except ValueError:
            invoice.invoice_date_raw = date_str

    invoice.seller_name = data.get("seller_name", "")
    invoice.seller_tax_id = data.get("seller_tax_id", "")
    invoice.buyer_name = data.get("buyer_name", "")
    invoice.buyer_tax_id = data.get("buyer_tax_id", "")
    invoice.total_amount = data.get("total_amount", "")
    invoice.total_tax = data.get("total_tax", "")
    invoice.amount_in_figures = data.get("amount_in_figures", "")

    pid = data.get("project_id", "")
    invoice.project_id = int(pid) if pid and str(pid).isdigit() else None


@router.get("/invoice/{invoice_id}/edit", name="main.invoice_edit")
async def invoice_edit_page(request: Request, invoice_id: int,
                            user: User = Depends(require_user),
                            db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return render(request, "errors/404.html", {}, status_code=404)
    return render(request, "invoice_edit.html", {
        "invoice": invoice,
        "projects": _sidebar_projects(db),
        "current_project_id": invoice.project_id,
    })


@router.post("/invoice/{invoice_id}/edit", dependencies=[Depends(verify_csrf)])
async def invoice_edit_submit(request: Request, invoice_id: int,
                              user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return render(request, "errors/404.html", {}, status_code=404)

    form = await request.form()
    data = {k: v for k, v in form.multi_items()}
    _apply_invoice_form(invoice, data, form)

    db.query(InvoiceItem).filter_by(invoice_id=invoice_id).delete()
    for item_data in _collect_items(form):
        db.add(InvoiceItem(invoice_id=invoice_id, **item_data))

    try:
        db.commit()
        flash(request, "发票信息更新成功")
        return RedirectResponse(f"/invoice/{invoice_id}", status_code=303)
    except Exception as e:
        db.rollback()
        logger.error("更新发票时出错: %s", e)
        flash(request, f"保存失败: {e}", "danger")
        return RedirectResponse(f"/invoice/{invoice_id}/edit", status_code=303)


@router.get("/invoice/{invoice_id}/delete", name="main.invoice_delete")
async def invoice_delete_page(request: Request, invoice_id: int,
                              user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return render(request, "errors/404.html", {}, status_code=404)
    return render(request, "confirm_delete.html", {
        "invoice": invoice,
        "projects": _sidebar_projects(db),
        "current_project_id": invoice.project_id,
    })


@router.post("/invoice/{invoice_id}/delete", dependencies=[Depends(verify_csrf)])
async def invoice_delete_submit(request: Request, invoice_id: int,
                                user: User = Depends(require_user),
                                db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return RedirectResponse("/", status_code=303)

    image_path = invoice.image_path
    db.delete(invoice)  # items 由 relationship cascade 一并删除
    db.commit()

    if image_path:
        full_path = os.path.join(get_config().upload_folder, image_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
        except OSError as e:
            logger.error("删除发票图片出错: %s", e)

    flash(request, "发票已删除")
    return RedirectResponse("/", status_code=303)


@router.get("/invoice/{invoice_id}/export/{fmt}", name="main.invoice_export")
async def invoice_export(request: Request, invoice_id: int, fmt: str,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    file_path = export_service.export_invoice(db, invoice_id, fmt)
    if not file_path or not os.path.exists(file_path):
        flash(request, "导出失败: 文件生成错误", "danger")
        return RedirectResponse(f"/invoice/{invoice_id}", status_code=303)
    return FileResponse(file_path, filename=os.path.basename(file_path),
                        media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.get("/projects", name="main.project_list")
async def project_list(request: Request,
                       user: User = Depends(require_user),
                       db: Session = Depends(get_db)):
    projects = _sidebar_projects(db)
    project_stats = {
        p.id: {"invoice_count": db.query(Invoice).filter_by(project_id=p.id).count()}
        for p in projects
    }
    unclassified = db.query(Invoice).filter(Invoice.project_id.is_(None)).count()
    return render(request, "project_list.html", {
        "projects": projects,
        "project_stats": project_stats,
        "unclassified_count": unclassified,
        "current_project_id": None,
    })


@router.get("/projects/create", name="main.project_create")
async def project_create_page(request: Request,
                              user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    return render(request, "project_form.html", {
        "title": "创建新项目",
        "projects": _sidebar_projects(db),
        "current_project_id": None,
    })


@router.post("/projects/create", dependencies=[Depends(verify_csrf)])
async def project_create_submit(request: Request,
                                name: str = Form(""),
                                description: str = Form(""),
                                user: User = Depends(require_user),
                                db: Session = Depends(get_db)):
    if not name.strip():
        flash(request, "项目名称不能为空", "danger")
        return RedirectResponse("/projects/create", status_code=303)
    db.add(Project(name=name.strip(), description=description))
    db.commit()
    flash(request, "项目创建成功")
    return RedirectResponse("/projects", status_code=303)


@router.get("/projects/{project_id}/edit", name="main.project_edit")
async def project_edit_page(request: Request, project_id: int,
                            user: User = Depends(require_user),
                            db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        return render(request, "errors/404.html", {}, status_code=404)
    return render(request, "project_form.html", {
        "title": "编辑项目",
        "project": project,
        "projects": _sidebar_projects(db),
        "current_project_id": project_id,
    })


@router.post("/projects/{project_id}/edit", dependencies=[Depends(verify_csrf)])
async def project_edit_submit(request: Request, project_id: int,
                              name: str = Form(""),
                              description: str = Form(""),
                              user: User = Depends(require_user),
                              db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        return RedirectResponse("/projects", status_code=303)
    if not name.strip():
        flash(request, "项目名称不能为空", "danger")
        return RedirectResponse(f"/projects/{project_id}/edit", status_code=303)
    project.name = name.strip()
    project.description = description
    db.commit()
    flash(request, "项目更新成功")
    return RedirectResponse("/projects", status_code=303)


@router.post("/projects/{project_id}/delete", name="main.project_delete",
             dependencies=[Depends(verify_csrf)])
async def project_delete(request: Request, project_id: int,
                         handle_invoices: str = Form("unclassify"),
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        return RedirectResponse("/projects", status_code=303)

    if handle_invoices == "unclassify":
        db.query(Invoice).filter_by(project_id=project_id).update(
            {Invoice.project_id: None})
    elif handle_invoices == "delete":
        for inv in db.query(Invoice).filter_by(project_id=project_id).all():
            db.delete(inv)  # items 由 relationship cascade 一并删除

    db.delete(project)
    db.commit()
    flash(request, "项目已删除")
    return RedirectResponse("/projects", status_code=303)


@router.get("/project/{project_id}", name="main.project_detail")
async def project_detail(request: Request, project_id: int,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        return render(request, "errors/404.html", {}, status_code=404)
    invoices = db.query(Invoice).filter_by(project_id=project_id).all()
    return render(request, "project_detail.html", {
        "title": f"项目: {project.name}",
        "project": project,
        "invoices": invoices,
        "projects": db.query(Project).order_by(Project.created_at.desc()).all(),
        "current_project_id": project_id,
    })


@router.get("/project/{project_id}/export", name="main.project_export")
async def project_export(request: Request, project_id: int,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    file_path = export_service.export_project(db, project_id)
    if not file_path or not os.path.exists(file_path):
        flash(request, "导出失败: 文件生成错误", "danger")
        return RedirectResponse(f"/project/{project_id}", status_code=303)
    return FileResponse(file_path, filename=os.path.basename(file_path),
                        media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def _effective_value(key: str, default: str = "") -> str:
    return Settings.get_value(key, "") or os.environ.get(key, default)


@router.get("/settings", name="main.settings")
async def settings_page(request: Request,
                        user: User = Depends(require_user)):
    return render(request, "settings.html", {
        "tencent_secret_id": _effective_value("TENCENT_SECRET_ID"),
        "tencent_secret_key": _effective_value("TENCENT_SECRET_KEY"),
        "vllm_api_key": _effective_value("VLLM_OCR_API_KEY"),
        "vllm_model": _effective_value("VLLM_OCR_MODEL", "deepseek-ai/DeepSeek-OCR"),
        "vllm_endpoint": _effective_value("VLLM_OCR_ENDPOINT", "https://api.siliconflow.cn/v1"),
    })


@router.post("/settings", dependencies=[Depends(verify_csrf)])
async def settings_submit(request: Request,
                          tencent_secret_id: str = Form(""),
                          tencent_secret_key: str = Form(""),
                          vllm_api_key: str = Form(""),
                          vllm_model: str = Form(""),
                          vllm_endpoint: str = Form(""),
                          user: User = Depends(require_user)):
    if not tencent_secret_id.strip() or not tencent_secret_key.strip():
        flash(request, "请填写腾讯云必填字段", "danger")
        return RedirectResponse("/settings", status_code=303)

    Settings.set_value("TENCENT_SECRET_ID", tencent_secret_id.strip())
    Settings.set_value("TENCENT_SECRET_KEY", tencent_secret_key.strip())
    if vllm_api_key.strip():
        Settings.set_value("VLLM_OCR_API_KEY", vllm_api_key.strip())
    if vllm_model.strip():
        Settings.set_value("VLLM_OCR_MODEL", vllm_model.strip())
    if vllm_endpoint.strip():
        Settings.set_value("VLLM_OCR_ENDPOINT", vllm_endpoint.strip())

    flash(request, "设置已保存", "success")
    return RedirectResponse("/", status_code=303)

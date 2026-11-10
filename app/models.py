"""ORM models. Table schema stays identical to the Flask version so
existing ``data/invoices.db`` files keep working; only ``ocr_tasks`` is new.
"""
from __future__ import annotations

import json
import decimal
import re
from datetime import datetime, timedelta
from decimal import Decimal

import bcrypt
import pyotp
from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from .database import Base, SessionLocal


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(32), nullable=True)

    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                        nullable=False)

    MAX_USERS = 1
    MAX_FAILED_LOGINS = 5
    LOCK_MINUTES = 15

    @classmethod
    def can_register(cls, db) -> bool:
        return db.query(cls).count() < cls.MAX_USERS

    @classmethod
    def get_owner(cls, db):
        return db.query(cls).first()

    def set_password(self, password: str) -> None:
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"),
                                  self.password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    def generate_mfa_secret(self) -> str:
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret

    def get_mfa_uri(self, issuer_name: str = "发票OCR系统") -> str:
        if not self.mfa_secret:
            self.generate_mfa_secret()
        return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
            name=self.email, issuer_name=issuer_name
        )

    def verify_mfa_code(self, code: str) -> bool:
        if not self.mfa_secret:
            return False
        return pyotp.TOTP(self.mfa_secret).verify(code, valid_window=1)

    def is_locked(self, db=None) -> bool:
        if self.locked_until and self.locked_until > datetime.now():
            return True
        if self.locked_until and self.locked_until <= datetime.now():
            self.locked_until = None
            self.failed_login_count = 0
            if db is not None:
                db.commit()
        return False

    def increment_failed_login(self, db) -> None:
        self.failed_login_count = (self.failed_login_count or 0) + 1
        if self.failed_login_count >= self.MAX_FAILED_LOGINS:
            self.locked_until = datetime.now() + timedelta(minutes=self.LOCK_MINUTES)
        db.commit()

    def reset_failed_login(self, db) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        db.commit()

    def record_login(self, db, ip_address: str) -> None:
        self.last_login_at = datetime.now()
        self.last_login_ip = ip_address
        self.reset_failed_login(db)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    invoices = relationship("Invoice", back_populates="project")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_type = Column(String(50), nullable=True)
    invoice_code = Column(String(50), nullable=True)
    invoice_number = Column(String(50), nullable=True)
    invoice_date = Column(Date, nullable=True)
    invoice_date_raw = Column(String(50), nullable=True)
    check_code = Column(String(100), nullable=True)
    machine_number = Column(String(50), nullable=True)

    seller_name = Column(String(100), nullable=True)
    seller_tax_id = Column(String(50), nullable=True)
    seller_address = Column(String(200), nullable=True)
    seller_bank_info = Column(String(200), nullable=True)

    buyer_name = Column(String(100), nullable=True)
    buyer_tax_id = Column(String(50), nullable=True)
    buyer_address = Column(String(200), nullable=True)
    buyer_bank_info = Column(String(200), nullable=True)

    total_amount = Column(String(50), nullable=True)
    total_tax = Column(String(50), nullable=True)
    amount_in_words = Column(String(100), nullable=True)
    amount_in_figures = Column(String(50), nullable=True)

    remarks = Column(String(200), nullable=True)
    payee = Column(String(50), nullable=True)
    reviewer = Column(String(50), nullable=True)
    issuer = Column(String(50), nullable=True)

    image_path = Column(String(200), nullable=True)
    json_data = Column(Text, nullable=True)

    doc_type = Column(String(50), nullable=True)
    extra_data = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("invoice_code", "invoice_number",
                         name="uix_invoice_code_number"),
    )

    project = relationship("Project", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice",
                         cascade="all, delete-orphan", lazy="selectin")

    @property
    def combined_id(self) -> str:
        if self.invoice_number:
            if self.invoice_code:
                return f"{self.invoice_code}{self.invoice_number}"
            return f"NO.{self.invoice_number}"
        return f"ID{self.id}"

    def get_total_amount_decimal(self) -> Decimal:
        try:
            cleaned = re.sub(r"[^\d.]", "", self.amount_in_figures or "0")
            return Decimal(cleaned) if cleaned else Decimal("0")
        except (ValueError, TypeError, decimal.InvalidOperation):
            return Decimal("0")

    def get_items(self) -> list:
        if not self.json_data:
            return []
        try:
            return json.loads(self.json_data).get("商品信息", [])
        except (json.JSONDecodeError, AttributeError):
            return []

    def get_extra_sections(self) -> dict:
        """Parse extra_data → type-specific sections (medical/train)."""
        if not self.extra_data:
            return {}
        try:
            blob = json.loads(self.extra_data)
            if isinstance(blob, dict) and isinstance(blob.get("sections"), dict):
                return blob["sections"]
        except (ValueError, TypeError):
            pass
        return {}


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    name = Column(String(100), nullable=True)
    specification = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(String(50), nullable=True)
    price = Column(String(50), nullable=True)
    amount = Column(String(50), nullable=True)
    tax_rate = Column(String(20), nullable=True)
    tax = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    invoice = relationship("Invoice", back_populates="items")

    @staticmethod
    def _strip_currency(v):
        if isinstance(v, str):
            return v.replace("¥", "").replace("￥", "").strip()
        return v

    @classmethod
    def from_item_data(cls, invoice_id: int, item_data: dict) -> "InvoiceItem":
        return cls(
            invoice_id=invoice_id,
            name=item_data.get("Name", item_data.get("项目名称",
                 item_data.get("LineNo", item_data.get("name", "")))),
            specification=item_data.get("Specification", item_data.get("规格型号",
                 item_data.get("Spec", item_data.get("specification", "")))),
            unit=item_data.get("Unit", item_data.get("单位", item_data.get("unit", ""))),
            quantity=item_data.get("Quantity", item_data.get("数量", item_data.get("quantity", ""))),
            price=cls._strip_currency(item_data.get("Price", item_data.get("单价",
                 item_data.get("UnitPrice", item_data.get("unit_price", ""))))),
            amount=cls._strip_currency(item_data.get("Amount", item_data.get("金额",
                 item_data.get("AmountWithoutTax", item_data.get("amount", ""))))),
            tax_rate=item_data.get("TaxRate", item_data.get("税率", item_data.get("tax_rate", ""))),
            tax=cls._strip_currency(item_data.get("Tax", item_data.get("税额",
                 item_data.get("TaxAmount", item_data.get("tax", ""))))),
        )


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Class-level helpers manage their own short-lived session so that
    # non-request code (e.g. core/ OCR clients) can read settings without
    # depending on the web layer.
    @classmethod
    def get_value(cls, key: str, default=None):
        with SessionLocal() as db:
            row = db.query(cls).filter_by(key=key).first()
            return row.value if row else default

    @classmethod
    def set_value(cls, key: str, value):
        with SessionLocal() as db:
            row = db.query(cls).filter_by(key=key).first()
            if row:
                row.value = value
            else:
                db.add(cls(key=key, value=value))
            db.commit()


class OcrTask(Base):
    """Async OCR job created by an upload; the frontend polls its status."""
    __tablename__ = "ocr_tasks"

    id = Column(Integer, primary_key=True)
    status = Column(String(20), default="pending", nullable=False)  # pending/running/done/failed
    filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    doc_type = Column(String(50), nullable=True)
    backend = Column(String(50), nullable=True)
    project_id = Column(Integer, nullable=True)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                        nullable=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.id,
            "status": self.status,
            "invoice_id": self.invoice_id,
            "error": self.error,
        }

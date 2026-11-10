"""baseline: full schema (users/projects/invoices/invoice_items/settings/ocr_tasks)

Existing deployments already have the first five tables via create_all —
for those, run ``alembic stamp head`` once instead of ``alembic upgrade``.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-11
"""
from __future__ import annotations

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all is idempotent and keeps this revision declarative-free of
    # duplicated column definitions; the models are the single source of truth.
    from app.database import Base
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind())

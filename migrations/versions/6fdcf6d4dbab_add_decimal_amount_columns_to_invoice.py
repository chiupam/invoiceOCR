"""add decimal amount columns to invoice

Revision ID: 6fdcf6d4dbab
Revises: 00a9278a5b2a
Create Date: 2026-04-16 03:37:10.065885

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '6fdcf6d4dbab'
down_revision = '00a9278a5b2a'
branch_labels = None
depends_on = None


def _clean_amount(amount_str):
    if not amount_str:
        return None
    import re
    cleaned = re.sub(r'[^\d.]', '', str(amount_str))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def upgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_amount_decimal', sa.Numeric(precision=12, scale=2), nullable=True))
        batch_op.add_column(sa.Column('total_tax_decimal', sa.Numeric(precision=12, scale=2), nullable=True))
        batch_op.add_column(sa.Column('amount_decimal', sa.Numeric(precision=12, scale=2), nullable=True))

    invoice = sa.table(
        'invoices',
        sa.column('id', sa.Integer),
        sa.column('total_amount', sa.String),
        sa.column('total_tax', sa.String),
        sa.column('amount_in_figures', sa.String),
        sa.column('total_amount_decimal', sa.Numeric),
        sa.column('total_tax_decimal', sa.Numeric),
        sa.column('amount_decimal', sa.Numeric),
    )

    conn = op.get_bind()
    results = conn.execute(text(
        "SELECT id, total_amount, total_tax, amount_in_figures FROM invoices"
    )).fetchall()

    for row in results:
        inv_id = row[0]
        total_amount_val = _clean_amount(row[1])
        total_tax_val = _clean_amount(row[2])
        amount_val = _clean_amount(row[3])

        if total_amount_val is not None or total_tax_val is not None or amount_val is not None:
            conn.execute(
                text(
                    "UPDATE invoices SET total_amount_decimal = :tam, "
                    "total_tax_decimal = :tt, amount_decimal = :ad WHERE id = :id"
                ),
                {
                    'tam': total_amount_val,
                    'tt': total_tax_val,
                    'ad': amount_val,
                    'id': inv_id,
                }
            )


def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('amount_decimal')
        batch_op.drop_column('total_tax_decimal')
        batch_op.drop_column('total_amount_decimal')

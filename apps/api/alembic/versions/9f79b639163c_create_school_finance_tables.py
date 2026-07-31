"""create_school_finance_tables

Revision ID: 9f79b639163c
Revises: 021
Create Date: 2026-07-30 22:52:17.384410
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f79b639163c'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('requires_reference', sa.Boolean(), nullable=False),
        sa.Column('gateway_config', sa.JSON(), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_table('fee_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fee_structure_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('installment_number', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('penalty_amount', sa.Integer(), nullable=False),
        sa.Column('discount_amount', sa.Integer(), nullable=False),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['fee_structure_id'], ['fee_structures.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fee_structure_id', 'installment_number', name='uq_fee_schedule_installment'),
    )
    op.create_table('transaction_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=30), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('fee_due_id', sa.Integer(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_before', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('recorded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['fee_due_id'], ['fee_dues.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key'),
    )
    op.create_index(op.f('ix_transaction_logs_created_at'), 'transaction_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_transaction_logs_fee_due_id'), 'transaction_logs', ['fee_due_id'], unique=False)
    op.create_index(op.f('ix_transaction_logs_payment_id'), 'transaction_logs', ['payment_id'], unique=False)
    op.create_index(op.f('ix_transaction_logs_student_id'), 'transaction_logs', ['student_id'], unique=False)
    op.create_index(op.f('ix_transaction_logs_transaction_type'), 'transaction_logs', ['transaction_type'], unique=False)
    op.create_table('payment_reconciliations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reconciliation_date', sa.Date(), nullable=False),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reconciled_by', sa.Integer(), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reconciled_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('receipt_number', sa.String(length=100), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('payment_method_name', sa.String(length=100), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('printed_count', sa.Integer(), nullable=False),
        sa.Column('generated_by', sa.Integer(), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id'),
        sa.UniqueConstraint('receipt_number'),
    )
    op.create_table('reconciliation_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reconciliation_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('expected_amount', sa.Integer(), nullable=False),
        sa.Column('actual_amount', sa.Integer(), nullable=False),
        sa.Column('difference', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['reconciliation_id'], ['payment_reconciliations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('finance_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('file_format', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('generated_by', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_finance_reports_report_type'), 'finance_reports', ['report_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_finance_reports_report_type'), table_name='finance_reports')
    op.drop_table('finance_reports')
    op.drop_table('reconciliation_items')
    op.drop_table('receipts')
    op.drop_table('payment_reconciliations')
    op.drop_index(op.f('ix_transaction_logs_transaction_type'), table_name='transaction_logs')
    op.drop_index(op.f('ix_transaction_logs_student_id'), table_name='transaction_logs')
    op.drop_index(op.f('ix_transaction_logs_payment_id'), table_name='transaction_logs')
    op.drop_index(op.f('ix_transaction_logs_fee_due_id'), table_name='transaction_logs')
    op.drop_index(op.f('ix_transaction_logs_created_at'), table_name='transaction_logs')
    op.drop_table('transaction_logs')
    op.drop_table('fee_schedules')
    op.drop_table('payment_methods')

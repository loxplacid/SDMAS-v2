"""create_report_builder_tables

Revision ID: 728914296ec8
Revises: 9f79b639163c
Create Date: 2026-07-31 00:21:46.542132
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '728914296ec8'
down_revision: Union[str, None] = '9f79b639163c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('allowed_roles', sa.JSON(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_report_definitions_code'), 'report_definitions', ['code'], unique=True)
    op.create_index(op.f('ix_report_definitions_category'), 'report_definitions', ['category'], unique=False)

    op.create_table('export_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('report_definition_id', sa.Integer(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('format', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('result_data', sa.Text(), nullable=True),
        sa.Column('result_filename', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['report_definition_id'], ['report_definitions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_export_jobs_user_id'), 'export_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_report_definition_id'), 'export_jobs', ['report_definition_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_status'), 'export_jobs', ['status'], unique=False)

    op.create_table('saved_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('report_definition_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('schedule', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['report_definition_id'], ['report_definitions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_saved_reports_user_id'), 'saved_reports', ['user_id'], unique=False)
    op.create_index(op.f('ix_saved_reports_report_definition_id'), 'saved_reports', ['report_definition_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_reports_report_definition_id'), table_name='saved_reports')
    op.drop_index(op.f('ix_saved_reports_user_id'), table_name='saved_reports')
    op.drop_table('saved_reports')
    op.drop_index(op.f('ix_export_jobs_status'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_report_definition_id'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_user_id'), table_name='export_jobs')
    op.drop_table('export_jobs')
    op.drop_index(op.f('ix_report_definitions_category'), table_name='report_definitions')
    op.drop_index(op.f('ix_report_definitions_code'), table_name='report_definitions')
    op.drop_table('report_definitions')

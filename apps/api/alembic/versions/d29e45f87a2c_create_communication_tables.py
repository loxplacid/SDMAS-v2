"""create_communication_tables

Revision ID: d29e45f87a2c
Revises: c09b48a8d73d
Create Date: 2026-07-31 02:38:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd29e45f87a2c'
down_revision: Union[str, None] = 'c09b48a8d73d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=20), nullable=False),
        sa.Column('channels', sa.JSON(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_message_templates_code'), 'message_templates', ['code'], unique=True)

    op.create_table('message_threads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('message_type', sa.String(length=20), nullable=False),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('communication_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('thread_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('channels', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('campus_id', sa.Integer(), nullable=True),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['template_id'], ['message_templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['thread_id'], ['message_threads.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_communication_messages_message_type'), 'communication_messages', ['message_type'], unique=False)
    op.create_index(op.f('ix_communication_messages_status'), 'communication_messages', ['status'], unique=False)
    op.create_index(op.f('ix_communication_messages_template_id'), 'communication_messages', ['template_id'], unique=False)
    op.create_index(op.f('ix_communication_messages_thread_id'), 'communication_messages', ['thread_id'], unique=False)

    op.create_table('communication_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_communication_preferences_user_id'), 'communication_preferences', ['user_id'], unique=False)

    op.create_table('message_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('recipient_type', sa.String(length=20), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['communication_messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_message_recipients_message_id'), 'message_recipients', ['message_id'], unique=False)
    op.create_index(op.f('ix_message_recipients_recipient_id'), 'message_recipients', ['recipient_id'], unique=False)
    op.create_index(op.f('ix_message_recipients_status'), 'message_recipients', ['status'], unique=False)

    op.create_table('message_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['communication_messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_message_attachments_message_id'), 'message_attachments', ['message_id'], unique=False)

    op.create_table('message_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('recurrence', sa.String(length=20), nullable=False),
        sa.Column('recurrence_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['communication_messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
    )
    op.create_index(op.f('ix_message_schedules_status'), 'message_schedules', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_message_schedules_status'), table_name='message_schedules')
    op.drop_table('message_schedules')
    op.drop_index(op.f('ix_message_attachments_message_id'), table_name='message_attachments')
    op.drop_table('message_attachments')
    op.drop_index(op.f('ix_message_recipients_status'), table_name='message_recipients')
    op.drop_index(op.f('ix_message_recipients_recipient_id'), table_name='message_recipients')
    op.drop_index(op.f('ix_message_recipients_message_id'), table_name='message_recipients')
    op.drop_table('message_recipients')
    op.drop_index(op.f('ix_communication_preferences_user_id'), table_name='communication_preferences')
    op.drop_table('communication_preferences')
    op.drop_index(op.f('ix_communication_messages_thread_id'), table_name='communication_messages')
    op.drop_index(op.f('ix_communication_messages_template_id'), table_name='communication_messages')
    op.drop_index(op.f('ix_communication_messages_status'), table_name='communication_messages')
    op.drop_index(op.f('ix_communication_messages_message_type'), table_name='communication_messages')
    op.drop_table('communication_messages')
    op.drop_table('message_threads')
    op.drop_index(op.f('ix_message_templates_code'), table_name='message_templates')
    op.drop_table('message_templates')

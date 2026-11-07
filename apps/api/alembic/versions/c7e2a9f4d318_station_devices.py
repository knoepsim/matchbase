"""table controllers of a Tournament Core: devices, their readings and where a result came from

Revision ID: c7e2a9f4d318
Revises: b6d1f3a8c529
Create Date: 2026-10-23 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7e2a9f4d318'
down_revision: str | Sequence[str] | None = 'b6d1f3a8c529'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = sa.Enum('MANUAL', 'SENSOR', name='resultsource')


def upgrade() -> None:
    op.create_table(
        'station_devices',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('station_id', sa.UUID(), nullable=True),
        sa.Column('sensor', sa.String(length=20), nullable=True),
        sa.Column('left_cups', sa.Integer(), nullable=True),
        sa.Column('right_cups', sa.Integer(), nullable=True),
        sa.Column('last_seq', sa.Integer(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station_id'),
    )
    op.create_table(
        'sensor_readings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('station_id', sa.UUID(), nullable=True),
        sa.Column('match_id', sa.UUID(), nullable=True),
        sa.Column('left_cups', sa.Integer(), nullable=False),
        sa.Column('right_cups', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['station_devices.id']),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sensor_readings_device_id', 'sensor_readings', ['device_id'])
    op.create_index('ix_sensor_readings_match_id', 'sensor_readings', ['match_id'])
    SOURCE.create(op.get_bind(), checkfirst=True)
    op.add_column('results', sa.Column('source', SOURCE, nullable=False, server_default='MANUAL'))


def downgrade() -> None:
    op.drop_column('results', 'source')
    SOURCE.drop(op.get_bind(), checkfirst=True)
    op.drop_index('ix_sensor_readings_match_id', table_name='sensor_readings')
    op.drop_index('ix_sensor_readings_device_id', table_name='sensor_readings')
    op.drop_table('sensor_readings')
    op.drop_table('station_devices')

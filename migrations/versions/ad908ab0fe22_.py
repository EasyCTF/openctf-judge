"""Add awaiting_verdict to jobstatus enum

Revision ID: ad908ab0fe22
Revises: 0c8799457ae0
Create Date: 2017-03-12 15:31:12.050102

"""

# revision identifiers, used by Alembic.
revision = 'ad908ab0fe22'
down_revision = '0c8799457ae0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('jobs', 'status', type_=sa.Enum('queued', 'cancelled', 'started', 'awaiting_verdict', 'finished',
                                                    name='jobstatus'), nullable=False)
    pass


def downgrade():
    op.alter_column('jobs', 'status', type_=sa.Enum('queued', 'cancelled', 'started', 'finished', name='jobstatus'),
                    nullable=False)
    pass

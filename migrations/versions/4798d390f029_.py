"""Add callback URL to

Revision ID: 4798d390f029
Revises: ad908ab0fe22
Create Date: 2017-03-13 16:31:43.543253

"""

# revision identifiers, used by Alembic.
revision = '4798d390f029'
down_revision = 'ad908ab0fe22'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column('jobs', sa.Column('callback_url', sa.UnicodeText(), nullable=True))


def downgrade():
    op.drop_column('jobs', 'callback_url')

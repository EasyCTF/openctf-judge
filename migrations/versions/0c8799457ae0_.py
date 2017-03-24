"""Add last modified timestamp for problems

Revision ID: 0c8799457ae0
Revises: 244aef0e654e
Create Date: 2017-03-05 11:54:30.259639

"""

# revision identifiers, used by Alembic.
revision = '0c8799457ae0'
down_revision = '244aef0e654e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('problems', sa.Column('last_modified', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_column('problems', 'last_modified')

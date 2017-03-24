"""Add support for source graders

Revision ID: 244aef0e654e
Revises: 85158bfe8859
Create Date: 2017-03-05 10:04:50.891855

"""

# revision identifiers, used by Alembic.
revision = '244aef0e654e'
down_revision = '85158bfe8859'

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column('problems', sa.Column('source_verifier_code', sa.UnicodeText(), nullable=True))
    op.add_column('problems', sa.Column('source_verifier_language', sa.Unicode(length=10), nullable=True))
    op.alter_column('jobs', 'verdict', type_=sa.Enum('accepted', 'ran', 'invalid_source', 'wrong_answer',
                                                     'time_limit_exceeded', 'memory_limit_exceeded',
                                                     'runtime_error', 'illegal_syscall', 'compilation_error',
                                                     'judge_error', name='jobverdict'))


def downgrade():
    op.drop_column('problems', 'source_verifier_language')
    op.drop_column('problems', 'source_verifier_code')

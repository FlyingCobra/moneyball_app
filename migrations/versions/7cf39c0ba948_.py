"""empty message

Revision ID: 7cf39c0ba948
Revises: c38de84e0327
Create Date: 2018-09-28 18:42:45.928592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7cf39c0ba948'
down_revision = 'c38de84e0327'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('rating', sa.Column('rating_type', sa.String(length=64), nullable=True))
    op.add_column('rating', sa.Column('rating_value', sa.Float(), nullable=True))
    op.create_index(op.f('ix_rating_rating_type'), 'rating', ['rating_type'], unique=False)
    with op.batch_alter_table('rating') as batch_op:
        batch_op.drop_column( 'trueskill')
        batch_op.drop_column( 'elo')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('rating', sa.Column('elo', sa.INTEGER(), nullable=True))
    op.add_column('rating', sa.Column('trueskill', sa.INTEGER(), nullable=True))
    op.drop_index(op.f('ix_rating_rating_type'), table_name='rating')
    op.drop_column('rating', 'rating_value')
    op.drop_column('rating', 'rating_type')
    # ### end Alembic commands ###

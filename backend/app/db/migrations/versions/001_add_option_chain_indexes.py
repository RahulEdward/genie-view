"""Add indexes for option chain queries

Revision ID: 001
Revises: 
Create Date: 2026-01-25 12:33:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite and individual indexes for option chain optimization"""
    # Composite index for option chain queries (name, exchange, expiry, option_type, strike)
    op.create_index(
        'idx_option_chain_query',
        'instrument_master',
        ['name', 'exchange', 'expiry', 'option_type', 'strike'],
        unique=False
    )
    
    # Index for expiry filtering
    op.create_index(
        'idx_instrument_expiry',
        'instrument_master',
        ['expiry'],
        unique=False
    )
    
    # Index for option type filtering
    op.create_index(
        'idx_instrument_option_type',
        'instrument_master',
        ['option_type'],
        unique=False
    )


def downgrade() -> None:
    """Remove the indexes"""
    op.drop_index('idx_instrument_option_type', table_name='instrument_master')
    op.drop_index('idx_instrument_expiry', table_name='instrument_master')
    op.drop_index('idx_option_chain_query', table_name='instrument_master')

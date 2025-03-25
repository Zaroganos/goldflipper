"""
Migration to add the WEM column to the wem_stocks table.

This migration adds the 'wem' column to the wem_stocks table to store the calculated
Weekly Expected Move value, fixing the display issue in the WEM module.
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..connection import get_db_connection

logger = logging.getLogger(__name__)

def upgrade() -> None:
    """
    Upgrade database schema by adding the wem column to wem_stocks table.
    """
    try:
        with get_db_connection() as session:
            # Check if column already exists
            check_query = text("""
                SELECT 1
                FROM pragma_table_info('wem_stocks')
                WHERE name = 'wem'
            """)
            
            result = session.execute(check_query).fetchone()
            
            if result:
                logger.info("WEM column already exists, skipping migration")
                return
                
            # Add wem column to wem_stocks table
            logger.info("Adding wem column to wem_stocks table...")
            add_column_query = text("""
                ALTER TABLE wem_stocks
                ADD COLUMN wem FLOAT
            """)
            
            session.execute(add_column_query)
            session.commit()
            
            logger.info("Successfully added wem column to wem_stocks table")
            
    except SQLAlchemyError as e:
        logger.error(f"Error during upgrade: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    upgrade() 
"""
Force Recreation of Database Tables

This script completely recreates all database tables to ensure they
match the model definitions exactly. It's a more aggressive approach
when migrations aren't working properly.

WARNING: This will delete all existing data in the affected tables.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def upgrade():
    """
    Forcibly recreate all database tables to match model definitions.
    This is a last resort when more targeted migrations aren't working.
    """
    from goldflipper.database.connection import get_db_connection
    from goldflipper.database.models import Base, WEMStock  # Import specific models we need to recreate
    
    logger.info("Starting forced table recreation...")
    
    try:
        with get_db_connection() as session:
            engine = session.get_bind()
            
            # Check if the tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            # For each model we want to recreate
            # Collect actual Table objects from the models we want to recreate
            models_to_recreate = [WEMStock.__table__]  # Add other model.__table__ entries as needed
            
            for table in models_to_recreate:
                table_name = table.name
                if table_name in tables:
                    logger.info(f"Dropping table {table_name}...")
                    # Drop the table
                    session.execute(text(f"DROP TABLE {table_name}"))
                    session.commit()
                    logger.info(f"Table {table_name} dropped successfully")
            
            # Recreate the tables based on model definitions
            logger.info("Recreating tables from model definitions...")
            Base.metadata.create_all(engine, tables=models_to_recreate)
            
            logger.info("Tables recreated successfully")
            
    except SQLAlchemyError as e:
        logger.error(f"Database error during table recreation: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during table recreation: {str(e)}")
        raise

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger.info("Running table recreation script ...")
    upgrade()
    logger.info("Completed table recreation") 